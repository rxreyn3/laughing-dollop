#!/usr/bin/env python3
import argparse
import calendar
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import vectorize_conversations as vc
from config import MONITORED_CHANNELS
from log_config import setup_logger
from slack_conversation_indexer import is_day_processed, process_channel_for_date

# Load environment variables
load_dotenv()

# Set up logger
logger = setup_logger(__name__)

# Database setup
engine = create_engine("sqlite:///conversations.db")
Session = sessionmaker(bind=engine)


def process_time_period(
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
        continuous_mode: Whether to run in continuous mode (always process)
        channel: Optional channel ID to process. If None, process all configured channels
    """
    # Step 1: Ingest conversations from Slack
    logger.info("\nStep 1: Ingesting conversations from Slack...")

    # Use specified channel or all monitored channels
    channels_to_process = [channel] if channel else MONITORED_CHANNELS

    for channel_id in channels_to_process:
        logger.info(f"Processing channel: {channel_id}")
        processed_count = 0
        skipped_count = 0
        current_date = start_date
        while current_date < end_date:
            with Session() as session:
                should_process = (
                    continuous_mode  # Always process in continuous mode
                    or force_update  # Process if force update is requested
                    or not is_day_processed(
                        session, channel_id, current_date
                    )  # Process if not already done
                )
                if should_process:
                    logger.debug(
                        f"Processing date: {current_date.strftime('%Y-%m-%d')}"
                    )
                    process_channel_for_date(session, channel_id, current_date)
                    processed_count += 1
                else:
                    skipped_count += 1
                    logger.debug(
                        f"Skipping date: {current_date.strftime('%Y-%m-%d')} (already processed)"
                    )
            current_date += timedelta(days=1)

        # Only show skipped count in date-range mode
        if continuous_mode:
            logger.info(
                f"Channel {channel_id} summary: processed {processed_count} days"
            )
        else:
            logger.info(
                f"Channel {channel_id} summary: processed {processed_count} days, "
                f"skipped {skipped_count} days"
            )

    # Step 2: Vectorize conversations
    logger.info("\nStep 2: Vectorizing conversations...")
    logger.info("Setting up ingestion pipeline...")
    pipeline = vc.setup_ingestion_pipeline()

    logger.info(
        f"Fetching conversations from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}..."
    )
    documents = vc.fetch_conversations(start_date, end_date, channel)
    if documents:
        logger.info(f"Vectorizing {len(documents)} conversations...")
        nodes = pipeline.run(documents=documents)
        logger.info(
            f"Vectorization complete: {len(nodes)} nodes created "
            f"(avg {len(nodes) / len(documents):.1f} nodes per conversation)"
        )
    else:
        logger.info("No new conversations to vectorize")


def process_date_range(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    force_update: bool = False,
    channel: Optional[str] = None,
) -> None:
    """
    Process conversations within a date range.

    Args:
        start_date: Start date (default: 1 month ago)
        end_date: End date (default: now)
        force_update: Whether to force update already processed days
        channel: Optional channel ID to process. If None, process all configured channels
    """
    if not start_date:
        start_date = datetime.now() - timedelta(days=30)
    if not end_date:
        end_date = datetime.now()

    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)

    logger.info(
        f"Processing conversations from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    )
    process_time_period(
        start_date,
        end_date,
        force_update=force_update,
        continuous_mode=False,
        channel=channel,
    )
    logger.info("Processing complete!")


def continuous_monitor(update_interval: int = 300) -> None:
    """
    Continuously monitor for new conversations and process them.

    Args:
        update_interval: Time in seconds between checks (default: 5 minutes)
    """
    logger.info(
        f"\nStarting continuous monitoring (checking every {update_interval} seconds)..."
    )
    logger.info("Press Ctrl+C to stop")

    try:
        while True:
            current_time = datetime.now()

            # Process from the start of the current day
            start_date = datetime(
                current_time.year, current_time.month, current_time.day
            )

            # Process until current time
            end_date = current_time

            try:
                logger.info(
                    f"\n[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] Checking for new conversations..."
                )
                process_time_period(start_date, end_date, continuous_mode=True)

            except Exception as e:
                logger.error(f"Error during processing: {e}")
                # Log the error but continue monitoring

            # Wait for next check
            logger.info(f"\nWaiting {update_interval} seconds before next check...")
            time.sleep(update_interval)

    except KeyboardInterrupt:
        logger.info("\nStopping continuous monitoring...")
        sys.exit(0)


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

    if args.mode == "continuous":
        logger.info("Starting continuous monitoring...")
        while True:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=1)
            process_time_period(
                start_date,
                end_date,
                force_update=args.force,
                continuous_mode=True,
                channel=args.channel,
            )
            time.sleep(300)  # Wait 5 minutes before next check
    else:
        process_date_range(
            start_date=args.start_date,
            end_date=args.end_date,
            force_update=args.force,
            channel=args.channel,
        )


if __name__ == "__main__":
    main()
