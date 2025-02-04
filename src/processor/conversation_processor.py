"""
Process and vectorize Slack conversations for semantic search.
"""

import logging
from typing import Dict, Any

from llama_index.core import Document, Settings
from llama_index.core.ingestion import (
    IngestionPipeline,
    IngestionCache,
    DocstoreStrategy,
)
from llama_index.core.node_parser import TokenTextSplitter

from src.config.llm_config import LLMConfig
from src.models.conversation import ConversationData

logger = logging.getLogger(__name__)


class ConversationProcessor:
    """
    Process and vectorize Slack conversations for semantic search.
    """

    def __init__(
            self, llm_config: LLMConfig, chunk_size: int = 384, chunk_overlap: int = 32
    ):
        """
        Initialize the conversation processor.

        Args:
            llm_config: Configuration for LLM and vector store components
            chunk_size: Size of text chunks for splitting (default: 384 tokens for text-embedding-3-small)
            chunk_overlap: Overlap between chunks (default: 32 tokens, ~8% overlap)
        """
        self.llm_config = llm_config

        # Initialize vector store
        self.vector_store = llm_config.get_vector_store()

        # Initialize document store in Redis
        self.doc_store = llm_config.get_document_store()

        # Initialize cache in Redis
        self.cache = IngestionCache(
            cache=llm_config.get_cache_store(),
            collection="slack_cache_collection",
        )

        # Initialize embedding model
        self.embed_model = llm_config.get_embedding_model()

        # Initialize text splitter
        self.text_splitter = TokenTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

        # Set up ingestion pipeline
        self.pipeline = IngestionPipeline(
            transformations=[self.text_splitter, self.embed_model],
            vector_store=self.vector_store,
            docstore=self.doc_store,
            cache=self.cache,
            docstore_strategy=DocstoreStrategy.UPSERTS,
        )

        # Update settings
        Settings.embed_model = self.embed_model
        Settings.node_parser = self.text_splitter

    def process_conversation(self, conversation: ConversationData) -> None:
        """
        Process a single conversation.

        Args:
            conversation: ConversationData instance
        """
        try:
            # Create document with metadata
            document = Document(
                text=conversation.content,
                metadata={
                    "thread_ts": conversation.thread_ts,
                    "channel_id": conversation.channel_id,
                    "channel_name": conversation.channel_name,
                    "date": conversation.date.isoformat(),
                    "participant_count": conversation.participant_count,
                }
            )

            # Process the document through pipeline
            nodes = self.pipeline.run(documents=[document])
            logger.info(
                f"Processed conversation from {conversation.channel_name} "
                f"into {len(nodes)} nodes"
            )

        except Exception as e:
            logger.error(f"Error processing conversation: {e}")
            raise
