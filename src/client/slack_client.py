"""
Slack API client with robust rate limiting and error handling.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging
import time

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)

class SlackClient:
    """
    A wrapper around the Slack Web API client that handles rate limiting and retries.
    """

    def __init__(self, token: str, max_retries: int = 3, initial_retry_delay: float = 1.0):
        """
        Initialize the Slack client.

        Args:
            token: Slack API token
            max_retries: Maximum number of retries for failed API calls
            initial_retry_delay: Initial delay between retries in seconds
        """
        self.client = WebClient(token=token)
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay

    def make_api_call(
        self,
        method_name: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make a Slack API call with retry logic for rate limits.

        Args:
            method_name: Name of the Slack API method to call
            **kwargs: Arguments to pass to the API method

        Returns:
            The API response

        Raises:
            SlackApiError: If all retries fail
        """
        method = getattr(self.client, method_name)
        last_exception = None
        retry_delay = self.initial_retry_delay

        for attempt in range(self.max_retries + 1):
            try:
                response = method(**kwargs)
                
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
                if attempt < self.max_retries:
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
                    
                    logger.error(f"API call failed (attempt {attempt + 1}/{self.max_retries + 1}): {str(e)}")
                    raise last_exception

            except Exception as e:
                logger.error(f"Unexpected error in API call: {str(e)}")
                raise

    def get_conversation_replies(
        self,
        channel: str,
        ts: str,
        oldest: Optional[str] = None,
        latest: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all replies in a conversation thread.

        Args:
            channel: Channel ID
            ts: Thread timestamp
            oldest: Start of time range
            latest: End of time range
            limit: Maximum number of messages to return

        Returns:
            List of message objects
        """
        try:
            result = self.make_api_call(
                "conversations_replies",
                channel=channel,
                ts=ts,
                oldest=oldest,
                latest=latest,
                limit=limit
            )
            return result["messages"]
        except Exception as e:
            logger.error(f"Error getting conversation replies: {str(e)}")
            raise

    def get_conversations(
        self,
        channel: str,
        oldest: Optional[str] = None,
        latest: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get conversations from a channel.

        Args:
            channel: Channel ID
            oldest: Start of time range
            latest: End of time range
            limit: Maximum number of conversations to return

        Returns:
            List of conversation objects
        """
        try:
            result = self.make_api_call(
                "conversations_history",
                channel=channel,
                oldest=oldest,
                latest=latest,
                limit=limit
            )
            return result["messages"]
        except Exception as e:
            logger.error(f"Error getting conversations: {str(e)}")
            raise

def main():
    """
    Development testing function.
    
    Usage:
        python -m src.client.slack_client
    """
    import os
    from dotenv import load_dotenv
    import json
    from datetime import datetime, timedelta

    # Load environment variables
    load_dotenv()
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        print("Error: SLACK_BOT_TOKEN not found in environment")
        return

    # Initialize client
    client = SlackClient(token)

    # Test conversation fetching
    channel = input("Enter channel ID to test (or press Enter for general): ") or "C04P5JNKP"
    days_ago = int(input("Enter number of days to look back (default: 7): ") or "7")

    # Calculate timestamps
    end_ts = datetime.now()
    start_ts = end_ts - timedelta(days=days_ago)

    print(f"\nFetching conversations from {start_ts.date()} to {end_ts.date()}...")
    
    try:
        # Get conversations
        messages = client.get_conversations(
            channel=channel,
            oldest=str(start_ts.timestamp()),
            latest=str(end_ts.timestamp())
        )

        print(f"\nFound {len(messages)} messages")
        
        # Process each thread
        thread_count = 0
        for msg in messages:
            if msg.get("thread_ts"):
                thread_count += 1
                print(f"\nThread {thread_count}:")
                thread = client.get_conversation_replies(
                    channel=channel,
                    ts=msg["thread_ts"]
                )
                print(json.dumps(thread[:2], indent=2))  # Show first 2 messages of thread
                if len(thread) > 2:
                    print(f"... and {len(thread)-2} more messages")

        print(f"\nSummary:")
        print(f"Total messages: {len(messages)}")
        print(f"Total threads: {thread_count}")

    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
