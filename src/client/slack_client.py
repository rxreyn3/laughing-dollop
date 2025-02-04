"""
Slack API client with rate limiting and error handling.
"""
import logging
import os
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


class SlackClient:
    """
    Slack API client with rate limiting and error handling.
    """

    def __init__(self, token: Optional[str] = None):
        """
        Initialize Slack client.

        Args:
            token: Slack API token. If not provided, uses SLACK_BOT_TOKEN env var.
        """
        if token is None:
            token = os.environ.get("SLACK_BOT_TOKEN")
        if not token:
            raise ValueError("Must specify token or set SLACK_BOT_TOKEN env var")

        self.client = WebClient(token=token)
        self._validate_auth()

    def _validate_auth(self) -> None:
        """Validate authentication token."""
        try:
            result = self.client.api_test()
            if not result["ok"]:
                raise ValueError(f"Error initializing Slack API: {result['error']}")
        except SlackApiError as e:
            raise ValueError(f"Error initializing Slack API: {str(e)}")

    def _handle_rate_limit(self, e: SlackApiError) -> None:
        """Handle rate limiting by waiting the specified time."""
        if e.response["error"] == "ratelimited":
            retry_after = int(e.response.headers.get("retry-after", "1"))
            logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
        else:
            raise

    def get_conversation_threads(self, channel_id: str, date: datetime) -> List[List[Dict[str, Any]]]:
        """
        Get all conversation threads from a channel for a specific date.

        Args:
            channel_id: Channel ID to get conversations from
            date: Date to get conversations for

        Returns:
            List of conversation threads, where each thread is a list of messages
        """
        start_ts = datetime(date.year, date.month, date.day, tzinfo=timezone.utc).timestamp()
        end_ts = datetime(date.year, date.month, date.day + 1, tzinfo=timezone.utc).timestamp()

        threads = []
        try:
            # Get all messages for the day
            while True:
                try:
                    result = self.client.conversations_history(
                        channel=channel_id,
                        oldest=str(start_ts),
                        latest=str(end_ts)
                    )
                    messages = result["messages"]

                    # Process each thread
                    for message in messages:
                        if message.get("thread_ts"):  # Only process threads
                            thread = self._get_thread_replies(channel_id, message["thread_ts"])
                            if thread:
                                threads.append(thread)

                    if not result["has_more"]:
                        break

                except SlackApiError as e:
                    self._handle_rate_limit(e)
                    continue

        except Exception as e:
            logger.error(f"Error getting conversations: {str(e)}")
            raise

        return threads

    def _get_thread_replies(self, channel_id: str, thread_ts: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get all replies in a thread.

        Args:
            channel_id: Channel ID
            thread_ts: Thread timestamp

        Returns:
            List of messages in the thread, or None if error
        """
        try:
            while True:
                try:
                    result = self.client.conversations_replies(
                        channel=channel_id,
                        ts=thread_ts
                    )
                    return result["messages"]

                except SlackApiError as e:
                    self._handle_rate_limit(e)
                    continue

        except Exception as e:
            logger.error(f"Error getting thread replies: {str(e)}")
            return None

    def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a user.

        Args:
            user_id: User ID to get info for

        Returns:
            User information dictionary or None if error
        """
        try:
            while True:
                try:
                    result = self.client.users_info(user=user_id)
                    return result["user"]

                except SlackApiError as e:
                    self._handle_rate_limit(e)
                    continue

        except Exception as e:
            logger.error(f"Error getting user info: {str(e)}")
            return None

def main():
    """
    Development testing function.
    
    Example usage:
        python -m src.client.slack_client
    """
    import sys
    from datetime import datetime, timedelta

    # Initialize client
    try:
        client = SlackClient()
    except ValueError as e:
        print(f"Error: {e}")
        print("Please set the SLACK_BOT_TOKEN environment variable")
        sys.exit(1)

    # Get channel ID from command line or use default
    channel_id = sys.argv[1] if len(sys.argv) > 1 else "C03ADA66PN3"  # hopper-support channel
    
    # Get threads from yesterday
    yesterday = datetime.now() - timedelta(days=1)
    try:
        threads = client.get_conversation_threads(channel_id, yesterday)
        print(f"\nFound {len(threads)} threads from {yesterday.strftime('%Y-%m-%d')} in channel {channel_id}")
        
        # Print thread info
        for i, thread in enumerate(threads, 1):
            parent = thread[0]  # First message is parent
            replies = thread[1:] if len(thread) > 1 else []
            
            print(f"\nThread {i}:")
            print(f"  Parent: {parent.get('text', '').split()[0]}...")
            print(f"  Replies: {len(replies)}")
            print(f"  Participants: {len({msg.get('user') for msg in thread})}")
            print(f"  Time: {datetime.fromtimestamp(float(parent['ts'])).strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Get some user info
            if parent.get('user'):
                user = client.get_user_info(parent['user'])
                if user:
                    print(f"  Posted by: {user.get('real_name', 'Unknown')}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
