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

The system provides three main interfaces:

1. **Data Ingestion**: Process and index Slack conversations
2. **Query Interface**: Search and retrieve conversation context
3. **Continuous Monitoring**: Real-time conversation tracking

### Initial Data Load
Process historical conversations within a date range:
```bash
python -m src.main --mode date-range --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```

### Channel-Specific Processing
Process conversations from specific channels:
```bash
python -m src.main --mode date-range --channel CHANNEL_ID
```

### Continuous Monitoring
Monitor and process new conversations in real-time:
```bash
python -m src.main --mode continuous [--channel CHANNEL_ID]
```

### Query Interface
Search and retrieve conversation context using natural language:
```bash
python query.py "Your question about Slack conversations"
```

### Configuration

#### Environment Variables

The system uses environment variables for configuration. Create a `.env` file with:

```env
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_APP_TOKEN=xapp-your-token-here

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=your-ada-002-deployment
AZURE_OPENAI_LLM_DEPLOYMENT=your-gpt-35-turbo-deployment

# Optional: API version for Azure OpenAI services
AZURE_EMBEDDING_API_VERSION=2023-05-15
AZURE_LLM_API_VERSION=2023-05-15

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=  # if required

# Required: Salt for anonymization of users
ANONYMIZATION_SALT=xxx
```

#### Channel Configuration

The system uses a YAML file to define which Slack channels to monitor. Create a `config/channels.yaml` file:

```yaml
channels:
  - id: "CHANNEL_ID"        # Slack channel ID
    name: "channel-name"    # Channel name for readability
    description: "Purpose"  # Channel description
    enabled: true          # Whether to monitor this channel

  # Example:
  - id: "C03ADA66PN3"
    name: "hopper-support"
    description: "General Hopper support channel"
    enabled: true
```

Each channel entry requires:
- `id`: Slack channel ID (get this from the channel URL or settings)
- `name`: Human-readable channel name
- `description`: Brief description of the channel's purpose
- `enabled`: Boolean flag to enable/disable monitoring (default: true)

The channel information is used for:
1. Determining which channels to monitor
2. Adding readable metadata to indexed conversations
3. Improving search results with channel context
4. Making logs and database queries more human-readable

## Development

### Project Structure
```
laughing-dollop/
├── src/
│   ├── client/
│   │   └── slack_client.py         # Slack API client with rate limiting
│   ├── config/
│   │   └── llm_config.py          # LLM and vector store configuration
│   ├── storage/
│   │   └── conversation_store.py   # SQLite-based conversation storage
│   ├── processor/
│   │   └── conversation_processor.py # Conversation vectorization
│   ├── indexer/
│   │   └── conversation_indexer.py # Indexing orchestration
│   ├── utils/
│   │   └── logging.py             # Logging utilities
│   ├── config.py                  # Application configuration
│   └── main.py                    # Main entry point
├── tests/
├── query.py                       # Query interface for RAG
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
