"""Pydantic models for the video schema."""

from datetime import datetime
from pydantic import BaseModel, Field


class VideoDocument(BaseModel):
    """Schema for a YouTube video document stored in MongoDB."""

    video_id: str
    channel_id: str
    channel_name: str
    title: str
    url: str
    upload_date: str
    view_count: int = 0
    like_count: int = 0
    description: str = ""
    thumbnail: str = ""
    tags: list[str] = Field(default_factory=list)
    inserted_at: datetime = Field(default_factory=datetime.utcnow)


class VideoResponse(BaseModel):
    """Lightweight response model for the /videos/latest endpoint."""

    title: str
    channel_name: str
    url: str
    upload_date: str
