"""
Main entry point for the Slack conversation indexer.
"""
import argparse
import logging
from datetime import datetime, timedelta
import time

from .config import Config
from .client.slack_client import SlackClient
from .storage.conversation_store import ConversationStore
from .processor.conversation_processor import ConversationProcessor
from .indexer.conversation_indexer import ConversationIndexer
from .utils.logging import setup_logger

# Configure logging
setup_logger()
logger = logging.getLogger(__name__)

def process_date_range(
    indexer: ConversationIndexer,
    start_date: datetime = None,
    end_date: datetime = None,
    force_update: bool = False,
    channel: str = None
) -> None:
    """
    Process conversations within a date range.

    Args:
        indexer: ConversationIndexer instance
        start_date: Start date (default: 1 month ago)
        end_date: End date (default: now)
        force_update: Whether to force update already processed days
        channel: Optional channel ID to process
    """
    if not start_date:
        start_date = datetime.now() - timedelta(days=30)
    if not end_date:
        end_date = datetime.now()

    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)

    logger.info(
        f"Processing conversations from {start_date.strftime('%Y-%m-%d')} "
        f"to {end_date.strftime('%Y-%m-%d')}"
    )
    
    indexer.process_time_period(
        start_date,
        end_date,
        force_update=force_update,
        continuous_mode=False,
        channel=channel
    )
    
    logger.info("Processing complete!")

def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Process and index Slack conversations."
    )
    parser.add_argument(
        "--mode",
        choices=["continuous", "date-range"],
        default="date-range",
        help="Processing mode",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force update already processed days",
    )
    parser.add_argument(
        "--start-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--channel",
        help="Process specific channel ID (optional)",
    )

    args = parser.parse_args()

    # Load configuration
    config = Config()
    if not config.is_valid:
        logger.error("Invalid configuration. Please check your environment variables.")
        return

    # Initialize components
    slack_client = SlackClient(config.slack_bot_token)
    conversation_store = ConversationStore(config.database_url)
    conversation_processor = ConversationProcessor(
        redis_url=config.redis_url,
        azure_endpoint=config.azure_endpoint,
        azure_deployment=config.azure_deployment,
        azure_api_key=config.azure_api_key,
        azure_api_version=config.azure_api_version
    )

    # Create indexer
    indexer = ConversationIndexer(
        slack_client=slack_client,
        conversation_store=conversation_store,
        conversation_processor=conversation_processor,
        monitored_channels=config.monitored_channels,
        anonymization_salt=config.anonymization_salt
    )

    if args.mode == "continuous":
        logger.info("Starting continuous monitoring...")
        while True:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=1)
            indexer.process_time_period(
                start_date,
                end_date,
                force_update=args.force,
                continuous_mode=True,
                channel=args.channel
            )
            time.sleep(300)  # Wait 5 minutes before next check
    else:
        process_date_range(
            indexer=indexer,
            start_date=args.start_date,
            end_date=args.end_date,
            force_update=args.force,
            channel=args.channel
        )

if __name__ == "__main__":
    main()
