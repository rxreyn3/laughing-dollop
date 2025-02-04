"""
SQLite-based storage for Slack conversations with change detection.
"""
import logging
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import blake3
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from src.models.conversation import ConversationData

logger = logging.getLogger(__name__)

# Get project root directory (2 levels up from this file)
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()

# Default database path in project root
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "conversations.db")
DEFAULT_DB_URL = f"sqlite:///{DEFAULT_DB_PATH}"

# Get database URL from environment or use default
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

Base = declarative_base()

class Conversation(Base):
    """Model for storing conversations."""
    __tablename__ = "conversations"

    thread_ts = Column(String, primary_key=True)
    channel_id = Column(String, nullable=False)
    channel_name = Column(String, nullable=False)  # Added for readability
    content_hash = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    last_updated = Column(DateTime, nullable=False)
    participant_count = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)

    def __repr__(self):
        return f"<Conversation(thread_ts={self.thread_ts}, channel={self.channel_name})>"

    def to_data_model(self) -> ConversationData:
        """Convert to ConversationData model."""
        return ConversationData.model_validate(self)

class ProcessedDay(Base):
    """Model for tracking processed days."""
    __tablename__ = "processed_days"

    id = Column(String, primary_key=True)  # Composite of channel_id + date
    channel_id = Column(String, nullable=False)
    channel_name = Column(String, nullable=False)  # Added for readability
    date = Column(Date, nullable=False)
    processed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<ProcessedDay(channel={self.channel_name}, date={self.date})>"

class ConversationStore:
    """
    Manages storage and retrieval of Slack conversations in SQLite.
    """

    def __init__(self, database_url: str = DATABASE_URL):
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
            channel_name="",  # Added for readability
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
        conversation: ConversationData
    ) -> bool:
        """
        Store or update a conversation in the database.

        Args:
            session: Database session
            conversation: ConversationData instance containing conversation data

        Returns:
            True if the conversation was updated, False if unchanged
        """
        content_hash = self._compute_content_hash(conversation.content)
        
        existing = session.query(Conversation).filter(
            Conversation.thread_ts == conversation.thread_ts
        ).first()

        if existing and existing.content_hash == content_hash:
            return False

        # Add computed fields
        conversation.content_hash = content_hash
        conversation.last_updated = datetime.now(timezone.utc)

        # Convert to dict for SQLAlchemy
        conversation_dict = conversation.model_dump()
        conversation_model = Conversation(**conversation_dict)

        try:
            session.merge(conversation_model)
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
    ) -> List[ConversationData]:
        """
        Retrieve conversations within a date range.

        Args:
            session: Database session
            start_date: Start date for filtering
            end_date: End date for filtering
            channel_id: Optional channel ID to filter by

        Returns:
            List of ConversationData instances
        """
        query = session.query(Conversation)

        if start_date:
            query = query.filter(Conversation.date >= start_date)
        if end_date:
            query = query.filter(Conversation.date < end_date)
        if channel_id:
            query = query.filter(Conversation.channel_id == channel_id)

        return [conversation.to_data_model() for conversation in query.all()]
