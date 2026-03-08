"""Historical data ingestion — fetch the latest videos from monitored channels using yt-dlp."""

import os
import sys
import json
import logging
import subprocess
from datetime import datetime, timezone

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.database import get_videos_collection
from app.config import CHANNEL_IDS, CHANNEL_HANDLES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MAX_VIDEOS = 1000


def fetch_channel_videos(channel_url: str, max_videos: int = MAX_VIDEOS) -> list[dict]:
    """Use yt-dlp to extract metadata for the latest videos from a channel.

    Args:
        channel_url: Full YouTube channel URL.
        max_videos: Maximum number of videos to fetch.

    Returns:
        List of video metadata dicts.
    """
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--dump-json",
        "--flat-playlist",
        "--no-download",
        "--playlist-end", str(max_videos),
        channel_url,
    ]

    logger.info("Running yt-dlp for %s (max %d videos)...", channel_url, max_videos)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600
        )
    except subprocess.TimeoutExpired:
        logger.error("yt-dlp timed out for %s", channel_url)
        return []

    if result.returncode != 0:
        logger.error("yt-dlp error: %s", result.stderr[:500])
        return []

    videos = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            videos.append(data)
        except json.JSONDecodeError:
            continue

    logger.info("Fetched %d video entries from %s", len(videos), channel_url)
    return videos


def transform_video(raw: dict, channel_id: str = "") -> dict:
    """Transform a yt-dlp flat-playlist entry into our MongoDB schema."""
    video_id = raw.get("id", raw.get("url", ""))

    upload_date_raw = raw.get("upload_date", "")
    if upload_date_raw and len(upload_date_raw) == 8:
        upload_date = f"{upload_date_raw[:4]}-{upload_date_raw[4:6]}-{upload_date_raw[6:8]}T00:00:00Z"
    else:
        upload_date = upload_date_raw

    # flat-playlist gives channel/uploader as null; fall back to playlist fields
    ch_name = (
        raw.get("channel")
        or raw.get("uploader")
        or raw.get("playlist_uploader_id", "").lstrip("@")
        or raw.get("playlist_uploader", "")
    )
    ch_id = (
        channel_id
        or raw.get("channel_id")
        or raw.get("playlist_id", "")
    )
    return {
        "video_id": video_id,
        "channel_id": ch_id,
        "channel_name": ch_name,
        "title": raw.get("title", ""),
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "upload_date": upload_date,
        "view_count": int(raw.get("view_count", 0) or 0),
        "like_count": int(raw.get("like_count", 0) or 0),
        "description": raw.get("description", "") or "",
        "thumbnail": raw.get("thumbnail", "") or "",
        "tags": raw.get("tags", []) or [],
        "inserted_at": datetime.now(timezone.utc),
    }


def ingest_channel(channel_url: str, channel_id: str = "", max_videos: int = MAX_VIDEOS):
    """Fetch and store videos for one channel."""
    col = get_videos_collection()
    raw_videos = fetch_channel_videos(channel_url, max_videos)

    inserted = 0
    for raw in raw_videos:
        doc = transform_video(raw, channel_id)
        if not doc["video_id"]:
            continue
        col.update_one(
            {"video_id": doc["video_id"]},
            {"$set": doc},
            upsert=True,
        )
        inserted += 1

    logger.info("Upserted %d videos from %s", inserted, channel_url)
    return inserted


def main():
    """Ingest historical data from all monitored channels."""
    logger.info("Starting historical ingestion...")

    total = 0
    for handle, channel_id in zip(CHANNEL_HANDLES, CHANNEL_IDS):
        channel_url = f"https://www.youtube.com/{handle}/videos"
        count = ingest_channel(channel_url, channel_id, MAX_VIDEOS)
        total += count

    logger.info("Historical ingestion complete. Total videos upserted: %d", total)


if __name__ == "__main__":
    main()
