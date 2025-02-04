# Slack Conversation Indexer and RAG System

A robust system for indexing Slack conversations and providing intelligent question-answering capabilities using Retrieval-Augmented Generation (RAG).

## Features

- **Conversation Monitoring**:
  - Multi-channel support with selective processing
  - Real-time content change detection
  - Incremental updates with day-level granularity
  - Robust rate limiting with Slack API compliance

- **Data Processing**:
  - Efficient conversation vectorization
  - Redis-based vector storage
  - BAAI/bge-reranker-large for semantic search
  - Context-aware RAG for accurate responses

- **Flexible Operation Modes**:
  - Date range processing for historical data
  - Continuous monitoring for real-time updates
  - Channel-specific processing options
  - Force update capability for data reprocessing

## Architecture

The system is built using modern Python best practices and consists of several key components:

### Core Components

1. **SlackClient**
   - Handles all Slack API interactions
   - Implements robust rate limiting and retry logic
   - Manages authentication and API responses

2. **ConversationStore**
   - SQLite-based conversation storage
   - Efficient change detection using Blake3 hashing
   - Tracks processed conversations and days

3. **ConversationProcessor**
   - Converts conversations to vector representations
   - Manages Redis vector storage
   - Handles document chunking and metadata

4. **ConversationIndexer**
   - Orchestrates the overall indexing process
   - Manages processing modes and scheduling
   - Coordinates between components

### Database Schema

1. **Conversation Table**
   ```sql
   - thread_ts (PK): Unique thread identifier
   - channel_id: Channel where thread exists
   - content_hash: Blake3 hash for change detection
   - content: Full thread text
   - last_updated: Update timestamp
   - participant_count: Number of participants
   - date: Thread creation date
   ```

2. **ProcessedDay Table**
   ```sql
   - id (PK): Composite of channel_id + date
   - channel_id: Channel identifier
   - date: Processed date
   - processed_at: UTC timestamp
   ```

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/slack-conversation-indexer.git
   cd slack-conversation-indexer
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   .\venv\Scripts\activate   # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables in `.env`:
   ```
   SLACK_BOT_TOKEN=xoxb-your-token-here
   SLACK_APP_TOKEN=xapp-your-token-here
   OPENAI_API_KEY=your-openai-key
   ```

## Usage

### Initial Data Load
```bash
python ingest_and_index.py --mode date-range --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```

### Channel-Specific Processing
```bash
python ingest_and_index.py --mode date-range --channel CHANNEL_ID
```

### Continuous Monitoring
```bash
python ingest_and_index.py --mode continuous [--channel CHANNEL_ID]
```

## Development

### Project Structure
```
laughing-dollop/
├── src/
│   ├── client/
│   │   └── slack_client.py
│   ├── storage/
│   │   └── conversation_store.py
│   ├── processor/
│   │   └── conversation_processor.py
│   ├── indexer/
│   │   └── conversation_indexer.py
│   ├── config.py
│   └── main.py
├── tests/
├── config.py
├── llama_config.py
├── log_config.py
├── query.py
├── slack_bot.py
├── slack_conversation_indexer.py
├── vectorize_conversations.py
├── ingest_and_index.py
├── requirements.txt
├── docker-compose.yml
└── Dockerfile
```

### Running Tests
```bash
pytest tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
