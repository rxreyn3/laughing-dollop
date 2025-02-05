"""Redis infrastructure setup for vector store, cache, and document store."""

from llama_index.core.ingestion import IngestionCache
from llama_index.storage.docstore.redis import RedisDocumentStore
from llama_index.storage.kvstore.redis import RedisKVStore
from llama_index.vector_stores.redis import RedisVectorStore
from redisvl.schema import IndexSchema

from src.models.config import RedisConfig
from src.utils.config import load_app_config
from src.utils.logger import logger


def create_redis_vector_schema() -> IndexSchema:
    """Create Redis vector store schema.

    Returns:
        Configured Redis vector store schema.
    """
    return IndexSchema.from_dict(
        {
            "index": {
                "name": "slack_conversations",
                "prefix": "conv",
            },
            "fields": [
                # Required fields for LlamaIndex
                {"type": "tag", "name": "id"},
                {"type": "tag", "name": "doc_id"},
                {"type": "text", "name": "text"},
                # Vector field for embeddings
                {
                    "type": "vector",
                    "name": "vector",
                    "attrs": {
                        "dims": 1536,  # text-embedding-ada-002 dimension
                        "algorithm": "hnsw",
                        "distance_metric": "cosine",
                    },
                },
                # Additional metadata fields
                {"type": "tag", "name": "channel_id"},
                {"type": "tag", "name": "channel_name"},
                {"type": "numeric", "name": "timestamp"},
            ],
        }
    )


def setup_redis_vector_store(config: RedisConfig) -> RedisVectorStore:
    """Set up Redis vector store.

    Args:
        config: Redis configuration.

    Returns:
        Configured Redis vector store.
    """
    try:
        redis_url = f"redis://{':' + config.password + '@' if config.password else ''}{config.host}:{config.port}"
        vector_store = RedisVectorStore(
            schema=create_redis_vector_schema(),
            redis_url=redis_url,
        )
        logger.info("Successfully configured Redis vector store")
        return vector_store
    except Exception as e:
        logger.error(f"Error setting up Redis vector store: {str(e)}")
        raise


def setup_redis_document_store(config: RedisConfig) -> RedisDocumentStore:
    """Set up Redis document store.

    Args:
        config: Redis configuration.

    Returns:
        Configured Redis document store.
    """
    try:
        doc_store = RedisDocumentStore.from_host_and_port(
            host=config.host,
            port=config.port,
            namespace="slack_docs",
        )
        logger.info("Successfully configured Redis document store")
        return doc_store
    except Exception as e:
        logger.error(f"Error setting up Redis document store: {str(e)}")
        raise


def setup_redis_cache(config: RedisConfig) -> IngestionCache:
    """Set up Redis cache for ingestion.

    Args:
        config: Redis configuration.

    Returns:
        Configured ingestion cache.
    """
    try:
        cache = IngestionCache(
            cache=RedisKVStore.from_host_and_port(
                host=config.host,
                port=config.port,
            ),
            collection="slack_cache",
        )
        logger.info("Successfully configured Redis cache")
        return cache
    except Exception as e:
        logger.error(f"Error setting up Redis cache: {str(e)}")
        raise


def configure_redis_infrastructure(
        config: RedisConfig,
) -> tuple[RedisVectorStore, RedisDocumentStore, IngestionCache]:
    """Configure complete Redis infrastructure.

    Args:
        config: Redis configuration.

    Returns:
        Tuple of (vector_store, document_store, cache).
    """
    try:
        # Set up all Redis components
        vector_store = setup_redis_vector_store(config)
        doc_store = setup_redis_document_store(config)
        cache = setup_redis_cache(config)

        logger.info("Successfully configured complete Redis infrastructure")
        return vector_store, doc_store, cache
    except Exception as e:
        logger.error(f"Error configuring Redis infrastructure: {str(e)}")
        raise


if __name__ == "__main__":
    _config = load_app_config()
    _vector_store, _doc_store, _cache = configure_redis_infrastructure(_config.redis)
