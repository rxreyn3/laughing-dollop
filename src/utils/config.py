"""Configuration loading and management."""
import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

from src.models.config import (
    AppConfig,
    RedisConfig,
    AzureOpenAIConfig,
    SlackConfig,
    ChannelConfig,
)
from src.utils.logger import logger


def load_env_config(env_path: Optional[str] = None) -> None:
    """Load environment variables from .env file.
    
    Args:
        env_path: Optional path to .env file. If None, searches in default locations.
    """
    if env_path and not os.path.exists(env_path):
        logger.warning(f"Specified .env file not found at {env_path}")
        return
    
    load_dotenv(env_path)
    logger.info("Loaded environment variables")


def load_channel_config(config_path: str) -> list[ChannelConfig]:
    """Load channel configuration from YAML file.
    
    Args:
        config_path: Path to the channel configuration YAML file.
        
    Returns:
        List of channel configurations.
    """
    if not os.path.exists(config_path):
        logger.error(f"Channel configuration file not found at {config_path}")
        return []
    
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
            
        channels = []
        for channel_data in config_data.get('channels', []):
            channel = ChannelConfig(**channel_data)
            channels.append(channel)
            
        logger.info(f"Loaded {len(channels)} channel configurations")
        return channels
    except Exception as e:
        logger.error(f"Error loading channel configuration: {str(e)}")
        return []


def load_app_config(
    env_path: Optional[str] = None,
    channel_config_path: Optional[str] = None
) -> AppConfig:
    """Load complete application configuration.
    
    Args:
        env_path: Optional path to .env file.
        channel_config_path: Optional path to channel configuration YAML file.
        
    Returns:
        Complete application configuration.
    """
    # Load environment variables
    load_env_config(env_path)
    
    # Load Redis configuration
    redis_config = RedisConfig(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', '6379')),
        password=os.getenv('REDIS_PASSWORD'),
    )
    
    # Load Azure OpenAI configuration
    azure_openai_config = AzureOpenAIConfig(
        api_key=os.getenv('AZURE_OPENAI_API_KEY', ''),
        endpoint=os.getenv('AZURE_OPENAI_ENDPOINT', ''),
        embedding_deployment=os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT', ''),
        llm_deployment=os.getenv('AZURE_OPENAI_LLM_DEPLOYMENT', ''),
        embedding_api_version=os.getenv('AZURE_EMBEDDING_API_VERSION', '2023-05-15'),
        llm_api_version=os.getenv('AZURE_LLM_API_VERSION', '2023-05-15'),
    )
    
    # Load Slack configuration
    slack_config = SlackConfig(
        bot_token=os.getenv('SLACK_BOT_TOKEN', ''),
        app_token=os.getenv('SLACK_APP_TOKEN', ''),
    )
    
    # Load channel configuration
    channels = []
    if channel_config_path:
        channels = load_channel_config(channel_config_path)
    
    # Create complete configuration
    config = AppConfig(
        redis=redis_config,
        azure_openai=azure_openai_config,
        slack=slack_config,
        channels=channels,
    )
    
    logger.info("Loaded complete application configuration")
    return config
