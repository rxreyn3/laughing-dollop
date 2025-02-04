from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from dotenv import load_dotenv
from llama_index.core import Document
from llama_index.core.ingestion import (
    IngestionPipeline,
    IngestionCache,
    DocstoreStrategy,
)
from llama_index.core.node_parser import TokenTextSplitter
from sqlalchemy import create_engine, text

import llama_config as config
from log_config import setup_logger

# Set up logger
logger = setup_logger(__name__)

# Load environment variables
load_dotenv()


def get_db_connection():
    """Create database connection"""
    engine = create_engine("sqlite:///conversations.db")
    return engine.connect()


def fetch_conversations(
    start_date: datetime,
    end_date: datetime,
    channel: Optional[str] = None
) -> List[Document]:
    """
    Fetch conversations from the database within the given date range.

    Args:
        start_date: Start date to fetch from
        end_date: End date to fetch to
        channel: Optional channel ID to filter by. If None, fetch from all channels.

    Returns:
        List of Document objects containing conversation content
    """
    conn = get_db_connection()

    # Base query
    query = """
        SELECT thread_ts, content, participant_count, channel_id, date 
        FROM conversations 
        WHERE content IS NOT NULL
    """

    # Add date range filters if provided
    if start_date and end_date:
        query += " AND date >= :start_date AND date < :end_date"

    # Add channel filter if provided
    if channel:
        query += " AND channel_id = :channel"

    # Execute query with parameters
    result = conn.execute(
        text(query),
        (
            {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "channel": channel,
            }
            if start_date and end_date and channel
            else (
                {
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                }
                if start_date and end_date
                else {}
            )
        ),
    )

    # Convert to Documents
    documents = []
    for row in result:
        thread_ts, content, participant_count, channel_id, date = row
        if content:
            # Convert date string to datetime if it's not None
            if date:
                date = datetime.strptime(date.split()[0], "%Y-%m-%d")

            doc = Document(
                text=content,
                metadata={
                    "thread_ts": thread_ts,
                    "source": "slack_conversation",
                    "participant_count": participant_count,
                    "channel_id": channel_id,
                    "date": date.strftime("%Y-%m-%d") if date else None,
                },
                id_=f"thread_{thread_ts}",
            )
            documents.append(doc)

    logger.info(f"Fetched {len(documents)} conversations from database")
    conn.close()
    return documents


def get_date_range():
    """Get the available date range from the database"""
    conn = get_db_connection()
    query = text(
        "SELECT MIN(date) as min_date, MAX(date) as max_date FROM conversations"
    )
    result = conn.execute(query).fetchone()
    conn.close()

    min_date, max_date = result[0], result[1]
    if min_date and max_date:
        # Split the datetime string and take just the date part before converting
        return datetime.strptime(min_date.split()[0], "%Y-%m-%d"), datetime.strptime(
            max_date.split()[0], "%Y-%m-%d"
        )
    return None, None


def setup_ingestion_pipeline() -> IngestionPipeline:
    """Configure ingestion pipeline with Redis components and Azure OpenAI"""
    # Create ingestion pipeline with transformations
    pipeline = IngestionPipeline(
        transformations=[
            # Split conversations into token-sized chunks for better GPT-4 context
            TokenTextSplitter(chunk_size=1024, chunk_overlap=200),
            # Generate embeddings
            config.get_embedding_model(),
        ],
        # Store documents in Redis
        docstore=config.get_document_store(),
        # Store vectors in Redis
        vector_store=config.get_vector_store(),
        # Cache transformations in Redis
        cache=IngestionCache(
            cache=config.get_cache_store(),
            collection="slack_cache",
        ),
        # Handle document updates
        docstore_strategy=DocstoreStrategy.UPSERTS,
    )

    logger.info("Ingestion pipeline configured")
    return pipeline
