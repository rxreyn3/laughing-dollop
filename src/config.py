"""
Configuration management for the Slack conversation indexer.
"""
import os
from typing import List
from dotenv import load_dotenv

class Config:
    """
    Configuration management for the application.
    """

    def __init__(self):
        """Initialize configuration from environment variables."""
        load_dotenv()

        # Slack configuration
        self.slack_bot_token = self._get_env("SLACK_BOT_TOKEN")
        self.slack_app_token = self._get_env("SLACK_APP_TOKEN")
        self.monitored_channels = self._get_env(
            "MONITORED_CHANNELS",
            "").split(",")

        # User anonymization
        self.anonymization_salt = self._get_env(
            "ANONYMIZATION_SALT",
            None  # If not set, will use bot token as salt
        )

        # Database configuration
        self.database_url = self._get_env(
            "DATABASE_URL",
            "sqlite:///conversations.db"
        )

        # Redis configuration
        self.redis_url = self._get_env(
            "REDIS_URL",
            "redis://localhost:6379"
        )

        # Azure OpenAI configuration
        self.azure_endpoint = self._get_env("AZURE_OPENAI_ENDPOINT")
        self.azure_deployment = self._get_env("AZURE_OPENAI_DEPLOYMENT")
        self.azure_api_key = self._get_env("AZURE_OPENAI_API_KEY")
        self.azure_api_version = self._get_env(
            "AZURE_OPENAI_API_VERSION",
            "2023-05-15"
        )

    def _get_env(self, key: str, default: str = None) -> str:
        """
        Get an environment variable with optional default.

        Args:
            key: Environment variable name
            default: Default value if not set

        Returns:
            Environment variable value

        Raises:
            ValueError: If required variable is not set
        """
        value = os.getenv(key, default)
        if value is None:
            raise ValueError(f"Required environment variable {key} is not set")
        return value

    @property
    def is_valid(self) -> bool:
        """Check if all required configuration is present."""
        try:
            return all([
                self.slack_bot_token,
                self.slack_app_token,
                self.monitored_channels,
                self.azure_endpoint,
                self.azure_deployment,
                self.azure_api_key
            ])
        except ValueError:
            return False
