"""YouTube Data API v3 helper — fetches video metadata by ID."""

import logging
import requests

from app.config import YOUTUBE_API_KEY

logger = logging.getLogger(__name__)

YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"


def fetch_video_metadata(video_id: str) -> dict | None:
    """Fetch metadata for a single video from YouTube Data API v3.

    Returns a dict matching the VideoDocument schema, or None on failure.
    """
    params = {
        "part": "snippet,statistics",
        "id": video_id,
        "key": YOUTUBE_API_KEY,
    }
    try:
        resp = requests.get(YOUTUBE_VIDEO_URL, params=params, timeout=15)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            logger.warning("No items returned for video_id=%s", video_id)
            return None

        item = items[0]
        snippet = item["snippet"]
        stats = item.get("statistics", {})

        return {
            "video_id": video_id,
            "channel_id": snippet.get("channelId", ""),
            "channel_name": snippet.get("channelTitle", ""),
            "title": snippet.get("title", ""),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "upload_date": snippet.get("publishedAt", ""),
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "description": snippet.get("description", ""),
            "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            "tags": snippet.get("tags", []),
        }
    except requests.RequestException as exc:
        logger.error("YouTube API error for video_id=%s: %s", video_id, exc)
        return None
