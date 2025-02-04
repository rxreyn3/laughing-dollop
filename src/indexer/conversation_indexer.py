"""
Main orchestrator for the Slack conversation indexing system.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging
import hashlib

from ..client.slack_client import SlackClient
from ..storage.conversation_store import ConversationStore
from ..processor.conversation_processor import ConversationProcessor

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
        anonymization_salt: str = None
    ):
        """
        Initialize the conversation indexer.

        Args:
            slack_client: Initialized SlackClient
            conversation_store: Initialized ConversationStore
            conversation_processor: Initialized ConversationProcessor
            monitored_channels: List of channel IDs to monitor
            anonymization_salt: Salt for user ID anonymization (default: uses bot token)
        """
        self.slack_client = slack_client
        self.store = conversation_store
        self.processor = conversation_processor
        self.monitored_channels = monitored_channels
        self._user_id_map: Dict[str, str] = {}
        self._anonymization_salt = anonymization_salt or slack_client.token

    def _anonymize_user_id(self, user_id: str) -> str:
        """
        Create a consistent anonymous identifier for a user ID.

        Args:
            user_id: Original user ID

        Returns:
            Anonymized user identifier
        """
        if user_id not in self._user_id_map:
            # Create a salted hash of the user ID
            hasher = hashlib.sha256()
            hasher.update(f"{self._anonymization_salt}:{user_id}".encode())
            # Use first 8 characters of hash for the anonymous ID
            self._user_id_map[user_id] = f"User_{hasher.hexdigest()[:8]}"
        
        return self._user_id_map[user_id]

    def _process_message_text(self, text: str, user_mentions: List[str]) -> str:
        """
        Process message text to anonymize any user mentions.

        Args:
            text: Original message text
            user_mentions: List of user IDs mentioned in the text

        Returns:
            Processed text with anonymized user mentions
        """
        processed_text = text
        for user_id in user_mentions:
            # Replace both <@USER_ID> and raw USER_ID with anonymized version
            processed_text = processed_text.replace(f"<@{user_id}>", self._anonymize_user_id(user_id))
            processed_text = processed_text.replace(user_id, self._anonymize_user_id(user_id))
        return processed_text

    def process_channel_for_date(
        self,
        channel_id: str,
        date: datetime,
        session
    ) -> int:
        """
        Process all conversations in a channel for a specific date.

        Args:
            channel_id: Channel ID to process
            date: Date to process
            session: Database session

        Returns:
            Number of conversations processed
        """
        # Convert date to Unix timestamp
        start_ts = datetime(date.year, date.month, date.day).timestamp()
        end_ts = (date + timedelta(days=1)).timestamp()

        # Get conversations for the day
        conversations = self.slack_client.get_conversations(
            channel=channel_id,
            oldest=str(start_ts),
            latest=str(end_ts)
        )

        processed_count = 0
        for message in conversations:
            # Skip non-thread parent messages
            if not message.get("thread_ts"):
                continue

            # Get full thread
            thread = self.slack_client.get_conversation_replies(
                channel=channel_id,
                ts=message["thread_ts"]
            )

            # Extract all user IDs from the thread
            user_mentions = set()
            for msg in thread:
                if msg.get("user"):
                    user_mentions.add(msg["user"])
                # Extract user mentions from text (format: <@USER_ID>)
                if msg.get("text"):
                    mentions = [
                        uid.strip("<@>") 
                        for uid in msg["text"].split() 
                        if uid.startswith("<@") and uid.endswith(">")
                    ]
                    user_mentions.update(mentions)

            # Combine messages into conversation text with anonymized users
            content = "\n".join(
                f"{self._anonymize_user_id(msg.get('user', 'UNKNOWN'))}: "
                f"{self._process_message_text(msg.get('text', ''), list(user_mentions))}"
                for msg in thread
            )

            # Store conversation
            updated = self.store.store_conversation(
                session=session,
                thread_ts=message["thread_ts"],
                channel_id=channel_id,
                content=content,
                participant_count=len({msg.get("user") for msg in thread}),
                date=datetime.fromtimestamp(float(message["ts"]))
            )

            if updated:
                processed_count += 1

        # Mark day as processed
        self.store.mark_day_processed(session, channel_id, date)
        return processed_count

    def process_time_period(
        self,
        start_date: datetime,
        end_date: datetime,
        force_update: bool = False,
        continuous_mode: bool = False,
        channel: Optional[str] = None
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
                with self.store.Session() as session:
                    should_process = (
                        continuous_mode  # Always process in continuous mode
                        or force_update  # Process if force update is requested
                        or not self.store.is_day_processed(session, channel_id, current_date)  # Process if not already done
                    )
                    
                    if should_process:
                        logger.debug(f"Processing date: {current_date.strftime('%Y-%m-%d')}")
                        processed = self.process_channel_for_date(channel_id, current_date, session)
                        processed_count += processed
                    else:
                        skipped_count += 1
                        logger.debug(f"Skipping date: {current_date.strftime('%Y-%m-%d')} (already processed)")
                
                current_date += timedelta(days=1)

            # Only show skipped count in date-range mode
            if continuous_mode:
                logger.info(f"Channel {channel_id} summary: processed {processed_count} conversations")
            else:
                logger.info(
                    f"Channel {channel_id} summary: processed {processed_count} conversations, "
                    f"skipped {skipped_count} days"
                )

        # Step 2: Vectorize conversations
        logger.info("\nStep 2: Vectorizing conversations...")
        with self.store.Session() as session:
            conversations = self.store.get_conversations(
                session,
                start_date=start_date,
                end_date=end_date,
                channel_id=channel
            )
            
            if conversations:
                logger.info(f"Vectorizing {len(conversations)} conversations...")
                self.processor.process_conversations(conversations)
            else:
                logger.info("No new conversations to vectorize")
