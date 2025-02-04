import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Callable

import blake3
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer
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
    processed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


def make_api_call_with_retry(
        func: Callable,
        max_retries: int = 3,
        initial_retry_delay: float = 1.0,
        *args,
        **kwargs
) -> Dict[str, Any]:
    """
    Make a Slack API call with retry logic for rate limits.

    Args:
        func: The Slack API function to call
        max_retries: Maximum number of retries
        initial_retry_delay: Initial delay between retries in seconds
        *args: Positional arguments for the API function
        **kwargs: Keyword arguments for the API function

    Returns:
        The API response

    Raises:
        SlackApiError: If all retries fail
    """
    last_exception = None
    retry_delay = initial_retry_delay

    for attempt in range(max_retries + 1):
        try:
            response = func(*args, **kwargs)

            if not response["ok"]:
                error = response.get("error", "unknown_error")
                if error == "ratelimited":
                    # Get retry_after from headers or use default
                    retry_after = float(response.get("headers", {}).get("Retry-After", 60))
                    logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue

                raise SlackApiError(f"Slack API returned error: {error}", response)

            return response

        except SlackApiError as e:
            last_exception = e
            if attempt < max_retries:
                retry_after = None

                # Check for Retry-After header
                if hasattr(e.response, 'headers') and 'Retry-After' in e.response.headers:
                    retry_after = float(e.response.headers['Retry-After'])
                    logger.warning(f"Rate limited. Waiting {retry_after} seconds as specified by Slack...")
                elif "ratelimited" in str(e):
                    # If no header but we know it's rate limited, use exponential backoff
                    retry_after = retry_delay
                    retry_delay *= 2
                    logger.warning(f"Rate limited without Retry-After header. Using backoff: {retry_after} seconds...")

                if retry_after:
                    time.sleep(retry_after)
                    continue

                logger.error(f"API call failed (attempt {attempt + 1}/{max_retries + 1}): {str(e)}")
                raise last_exception

        except Exception as e:
            logger.error(f"Unexpected error in API call: {str(e)}")
            raise


def compute_content_hash(content: str) -> str:
    """Generate a deterministic hash of the conversation content."""
    return blake3.blake3(content.encode()).hexdigest()


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
        processed_at=datetime.now(timezone.utc))

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


Session = sessionmaker(bind=engine)


def main():
    """Main function to process Slack conversations."""

    session = Session()

    channel_id = 'C061MH3FUN9'
    # Define the date to process (e.g., today)
    date_to_process = datetime(2024, 11, 29)

    print(f"Processing channel {channel_id} for date {date_to_process.strftime('%Y-%m-%d')}")
    process_channel_for_date(session, channel_id, date_to_process)

    # Close the session
    session.close()
    print("Processing complete.")


if __name__ == "__main__":
    main()
