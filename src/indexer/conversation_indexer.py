"""
Main orchestrator for the Slack conversation indexing system.
"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from llama_index.core import Document

from src.client.slack_client import SlackClient
from src.config.channel_config import ChannelConfig
from src.models.conversation import ConversationData
from src.processor.conversation_processor import ConversationProcessor
from src.storage.conversation_store import ConversationStore

logger = logging.getLogger(__name__)


class ConversationIndexer:
    """
    Orchestrates the ingestion, storage, and vectorization of Slack conversations.
    """

    def __init__(
        self,
        slack_client: SlackClient,
        conversation_store: ConversationStore,
        conversation_processor: ConversationProcessor,
        monitored_channels: List[str],
        channel_config: ChannelConfig,
    ):
        """
        Initialize the conversation indexer.

        Args:
            slack_client: Initialized SlackClient
            conversation_store: Initialized ConversationStore
            conversation_processor: Initialized ConversationProcessor
            monitored_channels: List of channel IDs to monitor
            channel_config: Channel configuration
        """
        self.slack_client = slack_client
        self.conversation_store = conversation_store
        self.conversation_processor = conversation_processor
        self.monitored_channels = monitored_channels
        self.channel_config = channel_config

    def _prepare_conversation_metadata(
        self, conversation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare metadata for conversation indexing."""
        channel = self.channel_config.get_channel_by_id(conversation["channel_id"])
        return {
            "thread_ts": conversation["thread_ts"],
            "channel_id": channel.id,
            "channel_name": channel.name,
            "channel_description": channel.description,
            "participant_count": conversation["participant_count"],
            "date": conversation["date"].isoformat(),
            "last_updated": conversation["last_updated"].isoformat(),
        }

    def process_conversation(self, conversation: ConversationData) -> None:
        """
        Process a single conversation.

        Args:
            conversation: ConversationData instance
        """
        try:
            # Get a database session
            session = self.conversation_store.Session()

            try:
                # Store conversation in database
                self.conversation_store.store_conversation(session, conversation)

                # Process conversation for vector search
                self.conversation_processor.process_conversation(conversation)

                logger.info(
                    f"Processed conversation from {conversation.channel_name} "
                    f"with {len(conversation.content.split())} words"
                )
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Error processing conversation: {e}")
            raise

    def process_channel_for_date(self, channel_id: str, date: datetime, session) -> int:
        """
        Process all conversations in a channel for a specific date.

        Args:
            channel_id: Channel ID to process
            date: Date to process
            session: Database session

        Returns:
            Number of conversations processed

        Raises:
            ValueError: If channel is not found in config
            Exception: For other processing errors
        """
        try:
            # Get channel info
            channel = self.channel_config.get_channel_by_id(channel_id)
            if not channel:
                raise ValueError(f"Channel {channel_id} not found in config")

            if not channel.enabled:
                logger.info(f"Skipping disabled channel: {channel_id}")
                return 0

            logger.info(
                f"Processing channel: {channel.name} ({channel_id}) for {date.strftime('%Y-%m-%d')}"
            )

            # Get all threads for the day
            threads = self.slack_client.get_conversation_threads(channel_id, date)
            if not threads:
                logger.info(
                    f"No threads found in {channel.name} for {date.strftime('%Y-%m-%d')}"
                )
                self.conversation_store.mark_day_processed(
                    session,
                    channel_id,
                    date,
                    channel_name=channel.name,  # Pass channel name from config
                )
                return 0

            processed_count = 0
            try:
                for thread in threads:
                    message = thread[0]  # First message is the parent
                    thread_ts = message["thread_ts"]

                    # Create user mapping for this thread
                    user_map = {}
                    for msg in thread:
                        user_id = msg.get("user", "Unknown")
                        if user_id and user_id not in user_map:
                            user_map[user_id] = f"User_{len(user_map) + 1}"

                    # Build conversation content in LLM-friendly format
                    content_parts = []

                    # First message is the conversation starter
                    starter = user_map[thread[0].get("user", "Unknown")]
                    content_parts.append(
                        f"{starter} started a topic with: {thread[0]['text']}"
                    )

                    # Add replies
                    if len(thread) > 1:
                        for msg in thread[1:]:
                            user = user_map[msg.get("user", "Unknown")]
                            content_parts.append(f"{user} replied with: {msg['text']}")

                    content = "\n".join(content_parts)

                    # Create conversation data
                    conversation = ConversationData(
                        thread_ts=thread_ts,
                        channel_id=channel_id,
                        channel_name=channel.name,
                        content=content,
                        participant_count=len(user_map),
                        date=datetime.fromtimestamp(float(message["ts"])),
                        last_updated=datetime.now(),
                        content_hash=None,  # Will be computed by conversation store
                    )

                    self.process_conversation(conversation)
                    processed_count += 1

                # Mark day as processed only if all threads were processed successfully
                self.conversation_store.mark_day_processed(
                    session,
                    channel_id,
                    date,
                    channel_name=channel.name,  # Pass channel name from config
                )
                logger.info(
                    f"Successfully processed {processed_count} threads from {channel.name} "
                    f"for {date.strftime('%Y-%m-%d')}"
                )
                return processed_count

            except Exception as e:
                logger.error(
                    f"Error processing threads in {channel.name} for {date.strftime('%Y-%m-%d')}: {e}"
                )
                raise

        except Exception as e:
            logger.error(f"Error processing channel {channel_id} for date {date}: {e}")
            raise

    def process_time_period(
        self,
        start_date: datetime,
        end_date: datetime,
        force_update: bool = False,
        continuous_mode: bool = False,
        channel: Optional[str] = None,
    ) -> None:
        """
        Process conversations for a given time period.

        Args:
            start_date: Start date to process from
            end_date: End date to process to
            force_update: Whether to force update already processed days
            continuous_mode: Whether running in continuous mode
            channel: Optional channel ID to process
        """
        # Step 1: Ingest conversations from Slack
        logger.info("\nStep 1: Ingesting conversations from Slack...")

        # Use specified channel or all monitored channels
        channels_to_process = [channel] if channel else self.monitored_channels

        for channel_id in channels_to_process:
            logger.info(f"Processing channel: {channel_id}")
            processed_count = 0
            skipped_count = 0

            current_date = start_date
            while current_date < end_date:
                with self.conversation_store.Session() as session:
                    should_process = (
                        continuous_mode  # Always process in continuous mode
                        or force_update  # Process if force update is requested
                        or not self.conversation_store.is_day_processed(
                            session, channel_id, current_date
                        )  # Process if not already done
                    )

                    if should_process:
                        logger.debug(
                            f"Processing date: {current_date.strftime('%Y-%m-%d')}"
                        )
                        processed = self.process_channel_for_date(
                            channel_id, current_date, session
                        )
                        processed_count += processed
                    else:
                        skipped_count += 1
                        logger.debug(
                            f"Skipping date: {current_date.strftime('%Y-%m-%d')} (already processed)"
                        )

                current_date += timedelta(days=1)

            # Only show skipped count in date-range mode
            if continuous_mode:
                logger.info(
                    f"Channel {channel_id} summary: processed {processed_count} conversations"
                )
            else:
                logger.info(
                    f"Channel {channel_id} summary: processed {processed_count} conversations, "
                    f"skipped {skipped_count} days"
                )

        # Step 2: Vectorize conversations
        logger.info("\nStep 2: Vectorizing conversations...")
        with self.conversation_store.Session() as session:
            conversations = self.conversation_store.get_conversations(
                session, start_date=start_date, end_date=end_date, channel_id=channel
            )

            if conversations:
                logger.info(f"Vectorizing {len(conversations)} conversations...")
                self.conversation_processor.process_conversations(conversations)
            else:
                logger.info("No new conversations to vectorize")
