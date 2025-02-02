# Slack Conversation Indexer

This bot monitors Slack conversations and maintains a local database of thread contents, allowing for efficient tracking and future analysis of conversations.

## Features

- Monitors multiple Slack channels
- Indexes conversation threads
- Stores conversation content with metadata in SQLite database
- Updates content when conversations change
- Runs hourly checks for updates

## Setup

1. Create a `.env` file in the project root with your Slack bot token:
   ```
   SLACK_BOT_TOKEN=xoxb-your-token-here
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the bot:
   ```
   python bot.py
   ```

## Database Schema

The SQLite database (`conversations.db`) contains the following information for each thread:

- `thread_ts`: Unique thread identifier (primary key)
- `channel_id`: Channel where the thread exists
- `content_hash`: Blake3 hash of the thread content
- `content`: Full text content of the thread
- `last_updated`: Timestamp of last update
- `participant_count`: Number of unique participants in the thread

## Next Steps

Future enhancements will include:
- Integration with vector databases
- RAG-based question-answering capabilities
- Advanced conversation analysis features
