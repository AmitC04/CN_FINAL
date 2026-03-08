"""Ingestion logic — upserts video metadata into MongoDB."""

import logging
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from app.database import get_videos_collection
from app.youtube_api import fetch_video_metadata

logger = logging.getLogger(__name__)


def upsert_video(video_data: dict) -> bool:
    """Insert or update a video document in MongoDB.

    Returns True if the document was written, False otherwise.
    """
    col = get_videos_collection()
    video_data["inserted_at"] = datetime.now(timezone.utc)
    try:
        col.update_one(
            {"video_id": video_data["video_id"]},
            {"$set": video_data},
            upsert=True,
        )
        logger.info("Upserted video: %s", video_data.get("title", video_data["video_id"]))
        return True
    except DuplicateKeyError:
        logger.debug("Duplicate video_id=%s, skipped.", video_data["video_id"])
        return False


def ingest_video_by_id(video_id: str) -> bool:
    """Fetch metadata from YouTube API and store in MongoDB."""
    meta = fetch_video_metadata(video_id)
    if meta is None:
        return False
    return upsert_video(meta)
