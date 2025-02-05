"""Azure OpenAI integration for LLM and embeddings."""

from llama_index.core import Settings
from llama_index.embeddings.azure_openai import AzureOpenAIEmbedding
from llama_index.llms.azure_openai import AzureOpenAI

from src.models.schemas import AzureOpenAIConfig
from src.utils.config import load_app_config
from src.utils.logger import logger


def setup_azure_llm(config: AzureOpenAIConfig) -> AzureOpenAI:
    """Set up Azure OpenAI LLM.

    Args:
        config: Azure OpenAI configuration.

    Returns:
        Configured Azure OpenAI LLM instance.
    """
    try:
        llm = AzureOpenAI(
            model="gpt-35-turbo-16k",  # Using 16k for longer context
            deployment_name=config.llm_deployment,
            api_key=config.api_key,
            azure_endpoint=str(config.endpoint),
            api_version=config.llm_api_version,
        )
        logger.info("Successfully configured Azure OpenAI LLM")
        return llm
    except Exception as e:
        logger.error(f"Error setting up Azure OpenAI LLM: {str(e)}")
        raise


def setup_azure_embeddings(config: AzureOpenAIConfig) -> AzureOpenAIEmbedding:
    """Set up Azure OpenAI embeddings.

    Args:
        config: Azure OpenAI configuration.

    Returns:
        Configured Azure OpenAI embedding instance.
    """
    try:
        embed_model = AzureOpenAIEmbedding(
            model="text-embedding-ada-002",
            deployment_name=config.embedding_deployment,
            api_key=config.api_key,
            azure_endpoint=str(config.endpoint),
            api_version=config.embedding_api_version,
        )
        logger.info("Successfully configured Azure OpenAI embeddings")
        return embed_model
    except Exception as e:
        logger.error(f"Error setting up Azure OpenAI embeddings: {str(e)}")
        raise


def configure_azure_openai(config: AzureOpenAIConfig) -> None:
    """Configure Azure OpenAI for both LLM and embeddings.

    Args:
        config: Azure OpenAI configuration.
    """
    try:
        # Set up LLM and embeddings
        llm = setup_azure_llm(config)
        embed_model = setup_azure_embeddings(config)

        # Configure global settings
        Settings.llm = llm
        Settings.embed_model = embed_model

        logger.info("Successfully configured Azure OpenAI integration")
    except Exception as e:
        logger.error(f"Error configuring Azure OpenAI: {str(e)}")
        raise


if __name__ == "__main__":
    config = load_app_config()
    configure_azure_openai(config.azure_openai)
    logger.info("Azure OpenAI integration configured")
