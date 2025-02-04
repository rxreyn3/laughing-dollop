# Slack Conversation Indexer and RAG System

A robust system for indexing Slack conversations and providing intelligent question-answering capabilities using Retrieval-Augmented Generation (RAG).

## Features

- **Conversation Monitoring**:
  - Multi-channel support with selective processing
  - Real-time content change detection using Blake3 hashing
  - Incremental updates with day-level granularity
  - Robust rate limiting with Slack API compliance

- **Data Processing**:
  - Type-safe data handling with Pydantic models
  - Efficient conversation vectorization with LlamaIndex
  - Redis-based vector and document storage
  - BAAI/bge-reranker-large for semantic search
  - Context-aware RAG for accurate responses

- **Flexible Operation Modes**:
  - Date range processing for historical data
  - Continuous monitoring for real-time updates
  - Channel-specific processing with YAML configuration
  - Force update capability for data reprocessing

## Architecture

The system is built using modern Python best practices and consists of several key components:

### Core Components

1. **SlackClient**
   - Handles all Slack API interactions with automatic rate limiting
   - Implements exponential backoff for retries
   - Supports thread-level conversation retrieval
   - Timezone-aware date handling

2. **ConversationStore**
   - SQLite-based conversation storage
   - Efficient change detection using Blake3 hashing
   - Transaction management for data consistency
   - Tracks processed conversations and days

3. **ConversationProcessor**
   - LlamaIndex-based document processing
   - Redis vector and document storage
   - Efficient caching with IngestionPipeline
   - Optimized text chunking for better results

4. **ConversationIndexer**
   - Orchestrates the overall indexing process
   - YAML-based channel configuration
   - Comprehensive error handling
   - Process tracking and monitoring

### Database Schema

#### Conversations Table
- `thread_ts` (PK): Unique thread identifier
- `channel_id`: Channel where thread exists
- `channel_name`: Human-readable channel name
- `content_hash`: Blake3 hash for change detection
- `content`: Full thread text content
- `last_updated`: Update timestamp
- `participant_count`: Number of unique participants
- `date`: Thread creation date

#### ProcessedDays Table
- `id` (PK): Composite of channel_id + date
- `channel_id`: Channel identifier
- `channel_name`: Human-readable channel name
- `date`: Processed date
- `processed_at`: UTC timestamp of processing

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/slack-conversation-indexer.git
   cd slack-conversation-indexer
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. Configure channels in `config/channels.yaml`:
   ```yaml
   channels:
     - id: "CHANNEL_ID"
       name: "channel-name"
       description: "Channel purpose"
       enabled: true
   ```

## Usage

1. Initial data load:
   ```bash
   python -m src.main --mode date-range --start-date YYYY-MM-DD --end-date YYYY-MM-DD
   ```

2. Channel-specific processing:
   ```bash
   python -m src.main --mode date-range --channel CHANNEL_ID
   ```

3. Continuous monitoring:
   ```bash
   python -m src.main --mode continuous [--channel CHANNEL_ID]
   ```

## Development

### Running Tests
```bash
pytest tests/
```

### Code Style
We follow PEP 8 guidelines. Format your code using:
```bash
black src/ tests/
```

### Type Checking
```bash
mypy src/
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [LlamaIndex](https://github.com/jerryjliu/llama_index) for the vectorization framework
- [BAAI/bge-reranker-large](https://huggingface.co/BAAI/bge-reranker-large) for semantic search
- Slack for their robust API
