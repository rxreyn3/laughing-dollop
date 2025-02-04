"""
Configuration for Slack channels.
"""
import os
from pathlib import Path
from typing import List

import yaml
from pydantic import BaseModel, Field


class SlackChannel(BaseModel):
    """Represents a Slack channel configuration."""
    id: str = Field(..., description="Slack channel ID")
    name: str = Field(..., description="Channel name")
    description: str = Field(..., description="Channel description")
    enabled: bool = Field(default=True, description="Whether the channel is enabled")


class ChannelList(BaseModel):
    """List of Slack channels."""
    channels: List[SlackChannel]


class ChannelConfig:
    """Configuration for Slack channels to monitor."""

    def __init__(self, config_path: str = None):
        """
        Initialize channel configuration.
        
        Args:
            config_path: Path to channels.yaml file. If not provided,
                       looks for config/channels.yaml relative to project root.
        """
        if config_path is None:
            # Default to config/channels.yaml in project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "channels.yaml"

        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Channel configuration file not found at {config_path}. "
                "Please create a channels.yaml file in the config directory."
            )

        # Load and validate configuration
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)
            self._config = ChannelList(**config_dict)

    @property
    def channels(self) -> List[SlackChannel]:
        """Get list of all channels."""
        return self._config.channels

    @property
    def enabled_channels(self) -> List[SlackChannel]:
        """Get list of enabled channels."""
        return [channel for channel in self.channels if channel.enabled]

    @property
    def enabled_channel_ids(self) -> List[str]:
        """Get list of enabled channel IDs."""
        return [channel.id for channel in self.enabled_channels]

    def get_channel_by_id(self, channel_id: str) -> SlackChannel:
        """
        Get channel configuration by ID.
        
        Args:
            channel_id: Slack channel ID to look up
            
        Returns:
            SlackChannel configuration
            
        Raises:
            ValueError: If channel_id is not found in configuration
        """
        for channel in self.channels:
            if channel.id == channel_id:
                return channel
        raise ValueError(f"Channel {channel_id} not found in configuration")

    def get_channel_name(self, channel_id: str) -> str:
        """
        Get channel name by ID.
        
        Args:
            channel_id: Slack channel ID to look up
            
        Returns:
            Channel name
            
        Raises:
            ValueError: If channel_id is not found in configuration
        """
        return self.get_channel_by_id(channel_id).name
