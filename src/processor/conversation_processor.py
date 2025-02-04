"""
Process and vectorize Slack conversations for semantic search.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional

from llama_index.core import Document, Settings
from llama_index.core.node_parser import TokenTextSplitter
from llama_index.vector_stores.redis import RedisVectorStore
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.ingestion import IngestionPipeline, IngestionCache
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import redis
import logging

logger = logging.getLogger(__name__)

class ConversationProcessor:
    """
    Process and vectorize Slack conversations for semantic search.
    """

    def __init__(
        self,
        redis_url: str,
        azure_endpoint: str,
        azure_deployment: str,
        azure_api_key: str,
        azure_api_version: str = "2023-05-15",
        chunk_size: int = 512,
        chunk_overlap: int = 20
    ):
        """
        Initialize the conversation processor.

        Args:
            redis_url: Redis connection URL
            azure_endpoint: Azure OpenAI endpoint
            azure_deployment: Azure OpenAI deployment name
            azure_api_key: Azure OpenAI API key
            azure_api_version: Azure OpenAI API version
            chunk_size: Size of text chunks for splitting
            chunk_overlap: Overlap between chunks
        """
        # Initialize Redis
        self.redis_client = redis.from_url(redis_url)
        
        # Initialize vector store
        self.vector_store = RedisVectorStore(
            redis_client=self.redis_client,
            index_name="slack_conversations",
            dim=1536  # Azure OpenAI embedding dimension
        )

        # Initialize document store in Redis
        self.doc_store = RedisVectorStore(
            redis_client=self.redis_client,
            index_name="slack_docs"
        )

        # Initialize cache in Redis
        self.cache = IngestionCache(
            redis_client=self.redis_client,
            cache_name="slack_cache"
        )

        # Initialize embedding models
        self.embed_model = AzureOpenAIEmbedding(
            model=azure_deployment,
            deployment_name=azure_deployment,
            api_key=azure_api_key,
            azure_endpoint=azure_endpoint,
            api_version=azure_api_version
        )

        # Initialize reranker model
        self.reranker = HuggingFaceEmbedding(
            model_name="BAAI/bge-reranker-large"
        )

        # Initialize text splitter
        self.text_splitter = TokenTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        # Set up ingestion pipeline
        self.pipeline = IngestionPipeline(
            transformations=[
                self.text_splitter,
                self.embed_model
            ],
            vector_store=self.vector_store,
            doc_store=self.doc_store,
            cache=self.cache
        )

        # Update settings
        Settings.embed_model = self.embed_model
        Settings.node_parser = self.text_splitter

    def _create_document(self, conversation: Dict[str, Any]) -> Document:
        """
        Create a Document object from a conversation.

        Args:
            conversation: Conversation dictionary from ConversationStore

        Returns:
            Document object ready for indexing
        """
        return Document(
            text=conversation["content"],
            metadata={
                "thread_ts": conversation["thread_ts"],
                "channel_id": conversation["channel_id"],
                "date": conversation["date"],
                "participant_count": conversation["participant_count"]
            }
        )

    def process_conversations(
        self,
        conversations: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> None:
        """
        Process and vectorize a list of conversations.

        Args:
            conversations: List of conversations from ConversationStore
            batch_size: Number of conversations to process in each batch
        """
        total_nodes = 0
        for i in range(0, len(conversations), batch_size):
            batch = conversations[i:i + batch_size]
            documents = [self._create_document(conv) for conv in batch]
            
            logger.info(f"Processing batch of {len(documents)} conversations...")
            
            # Process documents through the ingestion pipeline
            nodes = self.pipeline.run(documents=documents)
            total_nodes += len(nodes)
            
            logger.info(f"Processed {i + len(batch)}/{len(conversations)} conversations, created {len(nodes)} nodes")

        logger.info(
            f"Vectorization complete: {total_nodes} total nodes created "
            f"(avg {total_nodes / len(conversations):.1f} nodes per conversation)"
        )

    def search(
        self,
        query: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        channel_id: Optional[str] = None,
        limit: int = 5,
        rerank: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for conversations matching a query.

        Args:
            query: Search query
            start_date: Optional start date filter
            end_date: Optional end date filter
            channel_id: Optional channel filter
            limit: Maximum number of results
            rerank: Whether to use the reranker model

        Returns:
            List of matching conversations with scores
        """
        # Build metadata filters
        filters = {}
        if channel_id:
            filters["channel_id"] = channel_id
        if start_date:
            filters["date"] = lambda x: datetime.fromisoformat(x) >= start_date
        if end_date:
            if "date" in filters:
                old_filter = filters["date"]
                filters["date"] = lambda x: old_filter(x) and datetime.fromisoformat(x) < end_date
            else:
                filters["date"] = lambda x: datetime.fromisoformat(x) < end_date

        # Get more results if using reranker
        search_limit = limit * 3 if rerank else limit

        # Perform vector search
        results = self.vector_store.similarity_search_with_score(
            query,
            k=search_limit,
            filter_fn=lambda node: all(
                f(node.metadata.get(k, "")) 
                for k, f in filters.items()
            )
        )

        # Rerank results if requested
        if rerank and results:
            texts = [result[0].text for result in results]
            rerank_scores = self.reranker.get_cross_attention_scores(
                query,
                texts,
                normalize=True
            )
            
            # Combine vector similarity and reranking scores
            combined_results = [
                (node, (vec_score + rerank_score) / 2)
                for (node, vec_score), rerank_score 
                in zip(results, rerank_scores)
            ]
            
            # Sort by combined score and take top k
            results = sorted(
                combined_results,
                key=lambda x: x[1],
                reverse=True
            )[:limit]
        
        # Format results
        return [
            {
                "content": node.text,
                "score": float(score),  # Convert numpy float to Python float
                "metadata": node.metadata
            }
            for node, score in results
        ]
