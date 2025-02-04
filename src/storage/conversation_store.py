"""
SQLite-based storage for Slack conversations with change detection.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import logging

import blake3
from sqlalchemy import create_engine, Column, String, DateTime, Integer, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)
Base = declarative_base()

class Conversation(Base):
    """Model for storing conversation threads."""
    __tablename__ = 'conversations'

    thread_ts = Column(String, primary_key=True)
    channel_id = Column(String, nullable=False)
    content_hash = Column(String, nullable=False)
    content = Column(String, nullable=False)
    last_updated = Column(DateTime, nullable=False)
    participant_count = Column(Integer, nullable=False)
    date = Column(DateTime, nullable=False)

class ProcessedDay(Base):
    """Model for tracking processed days."""
    __tablename__ = 'processed_days'

    id = Column(String, primary_key=True)  # channel_id + date string
    channel_id = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)
    processed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

class ConversationStore:
    """
    Manages storage and retrieval of Slack conversations in SQLite.
    """

    def __init__(self, database_url: str = "sqlite:///conversations.db"):
        """
        Initialize the conversation store.

        Args:
            database_url: SQLAlchemy database URL
        """
        self.engine = create_engine(database_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def _compute_content_hash(self, content: str) -> str:
        """
        Compute a Blake3 hash of conversation content.

        Args:
            content: Conversation content to hash

        Returns:
            Hash of the content
        """
        return blake3.blake3(content.encode()).hexdigest()

    def _create_day_id(self, channel_id: str, date: datetime) -> str:
        """
        Create a unique ID for a processed day.

        Args:
            channel_id: Channel ID
            date: Date to process

        Returns:
            Unique ID combining channel and date
        """
        return f"{channel_id}_{date.strftime('%Y-%m-%d')}"

    def is_day_processed(self, session: Session, channel_id: str, date: datetime) -> bool:
        """
        Check if a specific day has been processed for a channel.

        Args:
            session: Database session
            channel_id: Channel ID
            date: Date to check

        Returns:
            True if the day has been processed
        """
        day_id = self._create_day_id(channel_id, date)
        return session.query(ProcessedDay).filter(ProcessedDay.id == day_id).first() is not None

    def mark_day_processed(self, session: Session, channel_id: str, date: datetime) -> None:
        """
        Mark a day as processed for a channel.

        Args:
            session: Database session
            channel_id: Channel ID
            date: Date to mark as processed
        """
        day_id = self._create_day_id(channel_id, date)
        processed_day = ProcessedDay(
            id=day_id,
            channel_id=channel_id,
            date=date,
            processed_at=datetime.now(timezone.utc)
        )
        try:
            session.merge(processed_day)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error marking day as processed: {str(e)}")
            raise

    def store_conversation(
        self,
        session: Session,
        thread_ts: str,
        channel_id: str,
        content: str,
        participant_count: int,
        date: datetime
    ) -> bool:
        """
        Store or update a conversation in the database.

        Args:
            session: Database session
            thread_ts: Thread timestamp
            channel_id: Channel ID
            content: Conversation content
            participant_count: Number of participants
            date: Conversation date

        Returns:
            True if the conversation was updated, False if unchanged
        """
        content_hash = self._compute_content_hash(content)
        
        existing = session.query(Conversation).filter(
            Conversation.thread_ts == thread_ts
        ).first()

        if existing and existing.content_hash == content_hash:
            return False

        conversation = Conversation(
            thread_ts=thread_ts,
            channel_id=channel_id,
            content_hash=content_hash,
            content=content,
            last_updated=datetime.now(timezone.utc),
            participant_count=participant_count,
            date=date
        )

        try:
            session.merge(conversation)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Error storing conversation: {str(e)}")
            raise

    def get_conversations(
        self,
        session: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        channel_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve conversations within a date range.

        Args:
            session: Database session
            start_date: Start date for filtering
            end_date: End date for filtering
            channel_id: Optional channel ID to filter by

        Returns:
            List of conversation dictionaries
        """
        query = session.query(Conversation)

        if start_date:
            query = query.filter(Conversation.date >= start_date)
        if end_date:
            query = query.filter(Conversation.date < end_date)
        if channel_id:
            query = query.filter(Conversation.channel_id == channel_id)

        conversations = query.all()
        return [
            {
                "thread_ts": conv.thread_ts,
                "channel_id": conv.channel_id,
                "content": conv.content,
                "participant_count": conv.participant_count,
                "date": conv.date.isoformat(),
                "last_updated": conv.last_updated.isoformat()
            }
            for conv in conversations
        ]
