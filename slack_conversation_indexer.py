import os
import time
from datetime import datetime
from typing import Optional, Dict, Any

import blake3
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from tqdm import tqdm

from config import MONITORED_CHANNELS

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


Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)


def compute_content_hash(content: str) -> str:
    """Generate a deterministic hash of the conversation content."""
    return blake3.blake3(content.encode()).hexdigest()


def make_api_call_with_retry(
    func, max_retries: int = 3, initial_delay: float = 1.0, *args, **kwargs
) -> Optional[Dict[str, Any]]:
    """Make an API call with exponential backoff retry logic for rate limits."""
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except SlackApiError as e:
            if e.response.get("error") == "ratelimited":
                retry_after = int(e.response.headers.get("Retry-After", delay))
                print(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                delay *= 2  # Exponential backoff
            else:
                raise
    return None


def fetch_thread_messages(channel_id: str, thread_ts: str):
    """Fetch all messages in a thread and format them as a structured conversation."""
    thread_result = make_api_call_with_retry(
        client.conversations_replies, channel=channel_id, ts=thread_ts
    )
    if thread_result is None:
        print(f"Failed to fetch thread {thread_ts} after retries")
        return None, 0

    messages = thread_result.get("messages", [])
    messages.sort(key=lambda x: float(x["ts"]))

    # Create a mapping of real users to anonymous identifiers
    user_map = {}
    user_counter = 1

    # Format the conversation in a structured way
    formatted_messages = []

    # First message is always the question/topic
    if messages:
        initial_msg = messages[0]
        initial_user = initial_msg.get("user", "Unknown")
        if initial_user not in user_map:
            user_map[initial_user] = f"User_{user_counter}"
            user_counter += 1

        formatted_messages.append(
            f"Initial Question/Topic (by {user_map[initial_user]}):\n{initial_msg.get('text', '')}\n"
        )

        # Format subsequent replies
        if len(messages) > 1:
            formatted_messages.append("\nResponses:")
            for msg in messages[1:]:
                user = msg.get("user", "Unknown")
                if user not in user_map:
                    user_map[user] = f"User_{user_counter}"
                    user_counter += 1

                text = msg.get("text", "")
                formatted_messages.append(f"\n{user_map[user]}: {text}")

    content = "\n".join(formatted_messages)
    reply_count = messages[0].get("reply_count", 0) if messages else 0
    return content, reply_count


def update_conversation_index():
    """Update the conversation index for recent threads."""
    session = Session()
    inserts = 0
    updates = 0
    try:
        # Use configured list of channels
        for channel_id in tqdm(MONITORED_CHANNELS, desc="Processing channels"):
            # Fetch recent conversations
            try:
                result = make_api_call_with_retry(
                    client.conversations_history,
                    channel=channel_id,
                    oldest=f"{time.time() - 86400 * 14:.6f}",  # Last 10 days, formatted as "1234567890.123456"
                )
                if result is None:
                    print(
                        f"Failed to fetch history for channel {channel_id} after retries"
                    )
                    continue

                messages = result.get("messages", [])
                for message in tqdm(
                    messages, desc=f"Processing messages in {channel_id}", leave=False
                ):
                    if "thread_ts" in message:
                        thread_ts = message["thread_ts"]

                        # Fetch thread content
                        content, participant_count = fetch_thread_messages(
                            channel_id, thread_ts
                        )

                        if content:
                            content_hash = compute_content_hash(content)

                            # Check if thread exists and has changed
                            existing = (
                                session.query(Conversation)
                                .filter_by(thread_ts=thread_ts)
                                .first()
                            )

                            if existing:
                                if existing.content_hash != content_hash:
                                    existing.content = content
                                    existing.content_hash = content_hash
                                    existing.last_updated = datetime.now()
                                    existing.participant_count = participant_count
                                    updates += 1
                            else:
                                new_conv = Conversation(
                                    thread_ts=thread_ts,
                                    channel_id=channel_id,
                                    content=content,
                                    content_hash=content_hash,
                                    last_updated=datetime.now(),
                                    participant_count=participant_count,
                                )
                                session.add(new_conv)
                                inserts += 1

                            session.commit()

            except SlackApiError as e:
                print(f"Error processing channel {channel_id}: {e}")

        print(
            f"Indexing complete - Inserted: {inserts}, Updated: {updates} conversations"
        )
    except Exception as e:
        print(f"Error updating conversation index: {e}")
    finally:
        session.close()


def main():
    # Schedule the indexing job to run every hour
    # schedule.every(1).hour.do(update_conversation_index)

    # Run initial indexing
    update_conversation_index()

    # Keep the script running
    # while True:
    #     schedule.run_pending()
    #     time.sleep(60)


if __name__ == "__main__":
    main()
