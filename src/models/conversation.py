"""
Models for conversation data.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ConversationData(BaseModel):
    """Model for conversation data passed between components."""
    thread_ts: str = Field(description="Thread timestamp (unique identifier)")
    channel_id: str = Field(description="Channel ID where conversation exists")
    channel_name: str = Field(description="Channel name for readability")
    content: str = Field(description="Full conversation content")
    participant_count: int = Field(description="Number of unique participants")
    date: datetime = Field(description="Original conversation date")
    last_updated: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    content_hash: Optional[str] = Field(default=None, description="Blake3 hash for change detection")

    class Config:
        """Pydantic model configuration."""
        from_attributes = True  # Allows conversion from SQLAlchemy model
