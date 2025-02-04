"""
Configuration for LLM and vector store components.
"""

import os

from dotenv import load_dotenv
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.storage.docstore.redis import RedisDocumentStore
from llama_index.storage.kvstore.redis import RedisKVStore
from llama_index.vector_stores.redis import RedisVectorStore
from redis import Redis
from redisvl.schema import IndexSchema


class LLMConfig:
    """Configuration for LLM and vector store components."""

    def __init__(self):
        """Initialize LLM configuration."""
        load_dotenv()

        # Azure OpenAI Configuration
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.api_version = os.getenv("AZURE_EMBEDDING_API_VERSION")
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.embedding_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        self.llm_deployment = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT")

        # Redis Configuration
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password = os.getenv("REDIS_PASSWORD", "")

        # Initialize Redis client
        self.redis_client = Redis(
            host=self.redis_host,
            port=self.redis_port,
            password=self.redis_password,
            decode_responses=False,  # Required for vector store binary data
        )

    def get_embedding_model(self) -> AzureOpenAIEmbedding:
        """Get Azure OpenAI embedding model."""
        return AzureOpenAIEmbedding(
            model=self.embedding_deployment,
            deployment_name=self.embedding_deployment,
            api_key=self.api_key,
            azure_endpoint=self.azure_endpoint,
            api_version=self.api_version,
        )

    def get_llm_model(self) -> AzureOpenAI:
        """Get Azure OpenAI LLM model."""
        return AzureOpenAI(
            model=self.llm_deployment,
            deployment_name=self.llm_deployment,
            api_key=self.api_key,
            azure_endpoint=self.azure_endpoint,
            api_version=self.api_version,
        )

    def get_redis_schema(self) -> IndexSchema:
        """Get Redis schema for vector store."""
        return IndexSchema.from_dict(
            {
                # Basic index configuration
                "index": {
                    "name": "slack_index",
                    "prefix": "slack",
                    "key_separator": ":",
                },
                # Fields to be indexed
                "fields": [
                    # Required fields for LlamaIndex
                    {"type": "tag", "name": "id"},
                    {"type": "tag", "name": "doc_id"},
                    {"type": "text", "name": "text"},
                    # Metadata fields for conversations
                    {"type": "tag", "name": "thread_ts"},
                    {"type": "tag", "name": "channel_id"},
                    {"type": "tag", "name": "channel_name"},
                    {"type": "numeric", "name": "participant_count"},
                    {"type": "numeric", "name": "date"},
                    {"type": "numeric", "name": "last_updated"},
                    # Vector field for embeddings
                    {
                        "type": "vector",
                        "name": "vector",
                        "attrs": {
                            "dims": 1536,  # Azure OpenAI ada-002 dimension
                            "algorithm": "hnsw",
                            "distance_metric": "cosine",
                        },
                    },
                ],
            }
        )

    def get_vector_store(self) -> RedisVectorStore:
        """Get Redis vector store."""
        return RedisVectorStore(
            redis_client=self.redis_client,
            schema=self.get_redis_schema(),
            overwrite=True,
        )

    def get_document_store(self) -> RedisDocumentStore:
        """Get Redis document store."""
        return RedisDocumentStore.from_redis_client(
            redis_client=self.redis_client, namespace="slack_docs"
        )

    def get_cache_store(self) -> RedisKVStore:
        """Get Redis cache store."""
        return RedisKVStore.from_redis_client(
            redis_client=self.redis_client
        )
