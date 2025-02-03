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
        start_date: datetime, end_date: datetime, force_update: bool = False, continuous_mode: bool = False
) -> None:
    """
    Process conversations for a given time period.

    Args:
        start_date: Start of the time period to process
        end_date: End of the time period to process
        force_update: Whether to force update existing conversations
        continuous_mode: Whether running in continuous monitoring mode
    """
    logger.info(
        f"Processing period: {start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')}"
    )

    # Step 1: Ingest conversations from Slack
    logger.info("\nStep 1: Ingesting conversations from Slack...")
    for channel_id in MONITORED_CHANNELS:
        logger.info(f"Processing channel: {channel_id}")
        processed_count = 0
        skipped_count = 0
        current_date = start_date
        while current_date < end_date:
            with Session() as session:
                should_process = (
                        continuous_mode  # Always process in continuous mode
                        or force_update  # Process if force update is requested
                        or not is_day_processed(session, channel_id, current_date)  # Process if not already done
                )
                if should_process:
                    logger.debug(f"Processing date: {current_date.strftime('%Y-%m-%d')}")
                    process_channel_for_date(session, channel_id, current_date)
                    processed_count += 1
                else:
                    skipped_count += 1
                    logger.debug(f"Skipping date: {current_date.strftime('%Y-%m-%d')} (already processed)")
            current_date += timedelta(days=1)

        # Only show skipped count in date-range mode
        if continuous_mode:
            logger.info(f"Channel {channel_id} summary: processed {processed_count} days")
        else:
            logger.info(
                f"Channel {channel_id} summary: processed {processed_count} days, "
                f"skipped {skipped_count} days (already processed)"
            )

    # Step 2: Vectorize conversations
    logger.info("\nStep 2: Vectorizing conversations...")
    logger.info("Setting up ingestion pipeline...")
    pipeline = vc.setup_ingestion_pipeline()

    logger.info(f"Fetching conversations from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
    documents = vc.fetch_conversations(start_date, end_date)
    if documents:
        logger.info(f"Found {len(documents)} conversations to vectorize")
        logger.info("Starting vectorization process...")
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
        interactive: bool = True,
) -> None:
    """
    Process conversations within a date range, optionally prompting for each month.

    Args:
        start_date: Start date of the range to process. If None, uses earliest date in DB.
        end_date: End date of the range to process. If None, uses latest date in DB.
        force_update: Whether to force update existing conversations
        interactive: Whether to prompt before processing each month
    """
    # If no dates provided, get them from the database
    if not start_date or not end_date:
        db_start, db_end = vc.get_date_range()
        if not db_start or not db_end:
            logger.error("No conversations found in the database!")
            return

        start_date = start_date or db_start
        end_date = end_date or db_end

    logger.info(
        f"\nProcessing range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    )

    # Start from the beginning of the month
    current_date = datetime(start_date.year, start_date.month, 1)

    while current_date <= end_date:
        # Calculate end of current month
        _, last_day = calendar.monthrange(current_date.year, current_date.month)
        month_end = datetime(
            current_date.year, current_date.month, last_day
        ) + timedelta(days=1)

        # Don't go beyond the end date
        month_end = min(month_end, end_date)

        # Process the current month
        process_time_period(current_date, month_end, force_update=force_update, continuous_mode=False)

        if current_date < end_date and interactive:
            while True:
                response = input(
                    "\nWould you like to process the next month? (y/n): "
                ).lower()
                if response in ["y", "n"]:
                    break
                logger.warning("Please enter 'y' for yes or 'n' for no.")

            if response == "n":
                logger.info("Exiting as requested.")
                break

        # Move to next month
        current_date = month_end

    logger.info("\nProcessing complete!")


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
    """Main entry point with command line argument parsing"""
    parser = argparse.ArgumentParser(
        description="Slack Conversation Ingestion and Indexing"
    )
    parser.add_argument(
        "--mode",
        choices=["date-range", "continuous"],
        required=True,
        help="Operation mode: date-range or continuous",
    )
    parser.add_argument(
        "--start-date",
        help="Start date for processing (YYYY-MM-DD)",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
    )
    parser.add_argument(
        "--end-date",
        help="End date for processing (YYYY-MM-DD)",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force update existing conversations",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run without prompting for each month",
    )
    parser.add_argument(
        "--update-interval",
        type=int,
        default=300,
        help="Update interval in seconds for continuous mode",
    )

    args = parser.parse_args()

    if args.mode == "date-range":
        process_date_range(
            start_date=args.start_date,
            end_date=args.end_date,
            force_update=args.force,
            interactive=not args.non_interactive,
        )
    else:  # continuous mode
        continuous_monitor(update_interval=args.update_interval)


if __name__ == "__main__":
    main()
