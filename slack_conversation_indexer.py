import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import blake3
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from sqlalchemy import (
    create_engine,
    Column,
    String,
    DateTime,
    Text,
    Integer,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from log_config import setup_logger

# Set up logger
logger = setup_logger(__name__)

# Load environment variables
load_dotenv()

# Initialize Slack client
client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

# Database setup
engine = create_engine("sqlite:///conversations.db")


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    """Model for storing conversation data."""

    __tablename__ = "conversations"

    thread_ts = Column(String, primary_key=True)
    channel_id = Column(String, nullable=False)
    content_hash = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    last_updated = Column(DateTime, nullable=False)
    participant_count = Column(Integer, default=0)
    date = Column(DateTime, nullable=False)


class ProcessedDay(Base):
    """Model for tracking which days have been processed for each channel."""

    __tablename__ = "processed_days"

    id = Column(String, primary_key=True)  # channel_id + date string
    channel_id = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)
    processed_at = Column(DateTime, nullable=False, default=datetime.utcnow)


Session = sessionmaker(bind=engine)


def compute_content_hash(content: str) -> str:
    """Generate a deterministic hash of the conversation content."""
    return blake3.blake3(content.encode()).hexdigest()


def make_api_call_with_retry(
    func, max_retries: int = 3, initial_delay: float = 1.0, *args, **kwargs
) -> Dict[str, Any]:
    """
    Make an API call with exponential backoff retry logic for rate limits.

    Args:
        func: The API function to call
        max_retries: Maximum number of retries
        initial_delay: Initial delay between retries in seconds
        *args: Positional arguments for the API function
        **kwargs: Keyword arguments for the API function

    Returns:
        The API response
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except SlackApiError as e:
            last_exception = e
            if e.response["error"] == "ratelimited":
                logger.warning(f"Rate limited. Waiting {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                raise

    raise last_exception


def fetch_thread_messages(channel_id: str, thread_ts: str) -> Optional[Dict[str, Any]]:
    """
    Fetch all messages in a thread and format them as a structured conversation.

    Args:
        channel_id: The Slack channel ID
        thread_ts: The thread timestamp

    Returns:
        A dictionary containing the formatted conversation data, or None if the thread
        is not found or there's an error
    """
    try:
        all_messages = []
        cursor = None

        while True:
            # Get the thread messages with pagination
            result = make_api_call_with_retry(
                client.conversations_replies,
                channel=channel_id,
                ts=thread_ts,
                limit=100,
                cursor=cursor,
            )

            if not result["ok"]:
                logger.error(f"Error fetching thread {thread_ts}: {result['error']}")
                return None

            messages = result["messages"]
            all_messages.extend(messages)

            # Check if there are more messages
            cursor = result.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        if not all_messages:
            return None

        # Create a mapping of user IDs to anonymous IDs within this thread
        user_map = {}
        for msg in all_messages:
            user_id = msg.get("user", "UNKNOWN")
            if user_id not in user_map:
                # Create a deterministic anonymous ID based on user_id and thread_ts
                hash_input = f"{user_id}:{thread_ts}"
                hash_value = blake3.blake3(hash_input.encode()).hexdigest()[:8]
                user_map[user_id] = f"User_{hash_value}"

        # Format the conversation
        formatted_content = ""
        participant_count = len(user_map)

        # First message is always the thread starter
        starter = all_messages[0]
        starter_ts = starter.get("ts", "")
        starter_user = user_map.get(starter.get("user", "UNKNOWN"), "UNKNOWN")
        starter_text = starter.get("text", "")
        formatted_content += f"[Thread Start][{starter_ts}] {starter_user}: {starter_text}\n"

        # Format replies
        for msg in all_messages[1:]:
            user = user_map.get(msg.get("user", "UNKNOWN"), "UNKNOWN")
            text = msg.get("text", "")
            ts = msg.get("ts", "")
            formatted_content += f"[Reply][{ts}] {user}: {text}\n"

        return {
            "thread_ts": thread_ts,
            "content": formatted_content.strip(),
            "participant_count": participant_count,
            "date": datetime.fromtimestamp(float(thread_ts)),
        }

    except Exception as e:
        logger.error(f"Error processing thread {thread_ts}: {e}")
        return None


def update_conversation_index(session, channel_id: str, thread_ts: str) -> None:
    """
    Update the conversation index for a specific thread.

    Args:
        session: The database session
        channel_id: The Slack channel ID
        thread_ts: The thread timestamp
    """
    conversation_data = fetch_thread_messages(channel_id, thread_ts)
    if not conversation_data:
        return

    content = conversation_data["content"]
    content_hash = compute_content_hash(content)

    # Check if conversation exists and needs updating
    existing = session.query(Conversation).filter_by(thread_ts=thread_ts).first()
    if existing:
        if existing.content_hash != content_hash:
            existing.content = content
            existing.content_hash = content_hash
            existing.last_updated = datetime.now()
            existing.participant_count = conversation_data["participant_count"]
    else:
        conversation = Conversation(
            thread_ts=thread_ts,
            channel_id=channel_id,
            content=content,
            content_hash=content_hash,
            last_updated=datetime.now(),
            participant_count=conversation_data["participant_count"],
            date=conversation_data["date"],
        )
        session.add(conversation)

    session.commit()


def is_day_processed(session, channel_id: str, date: datetime) -> bool:
    """
    Check if a specific day has been processed for a channel.

    Args:
        session: The database session
        channel_id: The Slack channel ID
        date: The date to check

    Returns:
        True if the day has been processed, False otherwise
    """
    day_id = f"{channel_id}_{date.strftime('%Y-%m-%d')}"
    return session.query(ProcessedDay).filter_by(id=day_id).first() is not None


def mark_day_processed(session, channel_id: str, date: datetime) -> None:
    """
    Mark a day as processed for a channel.
    If the day was already marked as processed, update its processed_at timestamp.

    Args:
        session: The database session
        channel_id: The Slack channel ID
        date: The date to mark as processed
    """
    day_id = f"{channel_id}_{date.strftime('%Y-%m-%d')}"
    processed_day = ProcessedDay(
        id=day_id,
        channel_id=channel_id,
        date=date,
        processed_at=datetime.utcnow(),
    )
    
    try:
        # Try to merge (update if exists, insert if not)
        session.merge(processed_day)
        session.commit()
    except Exception as e:
        logger.error(f"Error marking day as processed: {e}")
        session.rollback()
        raise


def process_channel_for_date(session, channel_id: str, date: datetime) -> None:
    """
    Process all conversations for a specific channel and date.

    Args:
        session: The database session
        channel_id: The Slack channel ID
        date: The date to process
    """
    start_time = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(days=1)

    try:
        all_messages = []
        cursor = None

        while True:
            # Get conversations for the channel within the time range with pagination
            result = make_api_call_with_retry(
                client.conversations_history,
                channel=channel_id,
                oldest=str(start_time.timestamp()),
                latest=str(end_time.timestamp()),
                limit=100,
                cursor=cursor,
            )

            if not result["ok"]:
                logger.error(f"Error fetching channel {channel_id}: {result['error']}")
                return

            messages = result.get("messages", [])
            all_messages.extend(messages)

            # Check if there are more messages
            cursor = result.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        # Process each thread
        thread_messages = [msg for msg in all_messages if msg.get("thread_ts")]
        if thread_messages:
            logger.info(
                f"Processing {len(thread_messages)} threads for {date.strftime('%Y-%m-%d')}"
            )
        else:
            logger.info(f"No threads found for {date.strftime('%Y-%m-%d')}")

        processed_threads = 0
        for msg in thread_messages:
            try:
                thread_ts = msg["thread_ts"]
                update_conversation_index(session, channel_id, thread_ts)
                processed_threads += 1
            except Exception as e:
                logger.error(f"Error processing thread {msg.get('thread_ts')}: {e}")
                session.rollback()
                continue

        if processed_threads > 0:
            # Only mark the day as processed if we successfully processed some threads
            try:
                mark_day_processed(session, channel_id, date)
                logger.info(f"Successfully processed {processed_threads} threads")
            except Exception as e:
                logger.error(f"Error marking day as processed: {e}")
                session.rollback()
        elif thread_messages:
            logger.warning(
                f"Found {len(thread_messages)} threads but none were successfully processed"
            )

    except Exception as e:
        logger.error(f"Error processing channel {channel_id} for date {date}: {e}")
        session.rollback()
        raise
