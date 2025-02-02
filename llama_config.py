import os
from dotenv import load_dotenv
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.vector_stores.redis import RedisVectorStore
from llama_index.storage.docstore.redis import RedisDocumentStore
from llama_index.storage.kvstore.redis import RedisKVStore
from redisvl.schema import IndexSchema

# Load environment variables
load_dotenv()

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_LLM_DEPLOYMENT = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT")
AZURE_EMBEDDING_API_VERSION = os.getenv("AZURE_EMBEDDING_API_VERSION", "2023-05-15")
AZURE_LLM_API_VERSION = os.getenv("AZURE_LLM_API_VERSION", "2023-05-15")

# Redis Configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}"


def get_embedding_model():
    """Get Azure OpenAI embedding model"""
    return AzureOpenAIEmbedding(
        model=AZURE_OPENAI_DEPLOYMENT,
        api_key=AZURE_OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_version=AZURE_EMBEDDING_API_VERSION,
    )


def get_llm_model():
    """Get Azure OpenAI LLM model"""
    return AzureOpenAI(
        model=AZURE_OPENAI_LLM_DEPLOYMENT,
        api_key=AZURE_OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_version=AZURE_LLM_API_VERSION,
    )


def get_redis_schema():
    """Get Redis vector store schema"""
    return IndexSchema.from_dict(
        {
            "index": {"name": "slack_conversations", "prefix": "conv"},
            "fields": [
                {"type": "tag", "name": "id"},
                {"type": "tag", "name": "doc_id"},
                {"type": "text", "name": "text"},
                {
                    "type": "vector",
                    "name": "vector",
                    "attrs": {
                        "dims": 1536,  # dimension for text-embedding-ada-002
                        "algorithm": "hnsw",
                        "distance_metric": "cosine",
                    },
                },
            ],
        }
    )


def get_vector_store():
    """Get Redis vector store"""
    return RedisVectorStore(
        schema=get_redis_schema(),
        redis_url=REDIS_URL,
    )


def get_document_store():
    """Get Redis document store"""
    return RedisDocumentStore.from_host_and_port(
        REDIS_HOST, REDIS_PORT, namespace="slack_docs"
    )


def get_cache_store():
    """Get Redis cache store"""
    return RedisKVStore.from_host_and_port(REDIS_HOST, REDIS_PORT)
