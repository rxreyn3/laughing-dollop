"""
Configuration for LLM and vector store components.
"""
import os
from typing import Optional

from dotenv import load_dotenv
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.storage.docstore.redis import RedisDocumentStore
from llama_index.storage.kvstore.redis import RedisKVStore
from llama_index.vector_stores.redis import RedisVectorStore
from redisvl.schema import IndexSchema

class LLMConfig:
    """Configuration for LLM and vector store components."""
    
    def __init__(self):
        """Initialize LLM configuration."""
        load_dotenv()
        
        # Azure OpenAI Configuration
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.embedding_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        self.llm_deployment = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT")
        self.embedding_api_version = os.getenv("AZURE_EMBEDDING_API_VERSION", "2023-05-15")
        self.llm_api_version = os.getenv("AZURE_LLM_API_VERSION", "2023-05-15")
        
        # Redis Configuration
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password = os.getenv("REDIS_PASSWORD")
    
    def get_embedding_model(self) -> AzureOpenAIEmbedding:
        """Get Azure OpenAI embedding model."""
        return AzureOpenAIEmbedding(
            model=self.embedding_deployment,
            deployment_name=self.embedding_deployment,
            api_key=self.api_key,
            azure_endpoint=self.endpoint,
            api_version=self.embedding_api_version
        )
    
    def get_llm_model(self) -> AzureOpenAI:
        """Get Azure OpenAI LLM model."""
        return AzureOpenAI(
            model=self.llm_deployment,
            deployment_name=self.llm_deployment,
            api_key=self.api_key,
            azure_endpoint=self.endpoint,
            api_version=self.llm_api_version
        )
    
    def get_redis_schema(self) -> IndexSchema:
        """Get Redis vector store schema."""
        return IndexSchema(
            prefix="slack",
            index_type="FLAT",
            dims=1536,  # Dimensions for Azure OpenAI ada-002
            metric="COSINE",
            data_type="FLOAT32",
            index_options={
                "TYPE": "FLAT",
                "DIM": 1536,
                "DISTANCE_METRIC": "COSINE",
                "INITIAL_CAP": 1000,
                "M": 40,
                "EF_CONSTRUCTION": 200,
            }
        )
    
    def get_vector_store(self) -> RedisVectorStore:
        """Get Redis vector store."""
        return RedisVectorStore(
            index_name="slack_index",
            index_schema=self.get_redis_schema(),
            redis_url=f"redis://{self.redis_host}:{self.redis_port}"
        )
    
    def get_document_store(self) -> RedisDocumentStore:
        """Get Redis document store."""
        return RedisDocumentStore(
            redis_url=f"redis://{self.redis_host}:{self.redis_port}"
        )
    
    def get_cache_store(self) -> RedisKVStore:
        """Get Redis cache store."""
        return RedisKVStore(
            redis_url=f"redis://{self.redis_host}:{self.redis_port}"
        )
