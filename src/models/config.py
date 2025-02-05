"""Configuration models for the application."""
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


class RedisConfig(BaseModel):
    """Redis configuration settings."""
    host: str = Field(default="localhost", description="Redis host address")
    port: int = Field(default=6379, description="Redis port number")
    password: Optional[str] = Field(default=None, description="Redis password")


class AzureOpenAIConfig(BaseModel):
    """Azure OpenAI configuration settings."""
    api_key: str = Field(..., description="Azure OpenAI API key")
    endpoint: HttpUrl = Field(..., description="Azure OpenAI endpoint URL")
    embedding_deployment: str = Field(..., description="Deployment name for embedding model")
    llm_deployment: str = Field(..., description="Deployment name for LLM model")
    embedding_api_version: str = Field(
        default="2023-05-15",
        description="API version for embedding service"
    )
    llm_api_version: str = Field(
        default="2023-05-15",
        description="API version for LLM service"
    )


class SlackConfig(BaseModel):
    """Slack API configuration settings."""
    bot_token: str = Field(..., description="Slack bot token")
    app_token: str = Field(..., description="Slack app token")


class ChannelConfig(BaseModel):
    """Configuration for a Slack channel."""
    id: str = Field(..., description="Channel ID")
    name: str = Field(..., description="Channel name")
    description: str = Field(..., description="Channel description")
    enabled: bool = Field(default=True, description="Whether the channel is enabled")


class AppConfig(BaseModel):
    """Main application configuration."""
    redis: RedisConfig = Field(default_factory=RedisConfig)
    azure_openai: AzureOpenAIConfig
    slack: SlackConfig
    channels: list[ChannelConfig] = Field(default_factory=list)
