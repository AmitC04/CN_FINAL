"""Agent tools — functions exposed to the Google ADK agent for MongoDB queries."""

import json
from app.query_service import (
    count_videos_by_channel,
    count_videos_about_keyword,
    get_latest_videos,
    get_videos_per_hour,
)


def tool_count_videos_by_channel(channel_name: str) -> str:
    """Count total videos stored in the database for a given channel name.

    Args:
        channel_name: The YouTube channel name to search for (e.g. 'markets', 'ANINewsIndia').

    Returns:
        A string with the count of videos for that channel.
    """
    count = count_videos_by_channel(channel_name)
    if count == 0:
        return (
            f"No videos found for '{channel_name}' right now. "
            "This may be because the database hasn't been populated yet — "
            "run `python scripts/ingest_history.py` to load historical data, "
            "or the live connection is temporarily unavailable."
        )
    return f"There are {count} videos from the '{channel_name}' channel stored in the database."


def tool_count_videos_about_keyword(keyword: str, hours: int = 24) -> str:
    """Count videos mentioning a keyword in title or description within the last N hours.

    Args:
        keyword: Keyword to search for in video titles and descriptions.
        hours: Number of hours to look back (default 24).

    Returns:
        A string with the count of matching videos.
    """
    count = count_videos_about_keyword(keyword, hours)
    return (
        f"Found {count} videos mentioning '{keyword}' in the last {hours} hours."
    )


def tool_get_latest_videos(limit: int = 5) -> str:
    """Return the latest videos stored in the database.

    Args:
        limit: Maximum number of videos to return (default 5).

    Returns:
        A JSON string listing the latest videos with title, channel, URL, and upload date.
    """
    videos = get_latest_videos(limit)
    if not videos:
        return (
            "No videos are currently available. "
            "The database may still be syncing or the connection is being re-established. "
            "Please run the historical ingestion script or try again in a moment."
        )
    return json.dumps(videos, indent=2, default=str)


def tool_get_videos_per_hour(hours: int = 24) -> str:
    """Get the number of videos published per hour for charting purposes.

    Args:
        hours: Number of hours to look back (default 24).

    Returns:
        A JSON string with hourly video counts for chart generation.
    """
    data = get_videos_per_hour(hours)
    if not data:
        return "No data available for the specified time range."
    return json.dumps(data, indent=2, default=str)
