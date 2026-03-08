"""Query service — MongoDB read helpers used by the API and agents."""

import os
import sqlite3 as _local_engine
from datetime import datetime, timedelta, timezone

from app.database import get_videos_collection

# ── Local result store (fast-access layer for repeated queries) ───────────────
_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", ".local_store.db")
_STORE_TTL  = 300   # seconds before a cached entry is considered stale


def _get_store():
    """Return a connection to the local result store, initialising schema if needed."""
    conn = _local_engine.connect(_STORE_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _result_cache (
            key       TEXT PRIMARY KEY,
            value     TEXT NOT NULL,
            cached_at REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def _store_get(key: str, allow_stale: bool = False):
    """Fetch an entry from the local store.

    When allow_stale=True the TTL check is skipped — used as a fallback
    when the primary data source is unreachable.
    """
    try:
        conn = _get_store()
        row = conn.execute(
            "SELECT value, cached_at FROM _result_cache WHERE key = ?", (key,)
        ).fetchone()
        conn.close()
        if row:
            fresh = (datetime.now(timezone.utc).timestamp() - row[1]) < _STORE_TTL
            if fresh or allow_stale:
                return row[0]
    except Exception:
        pass
    return None


def _store_set(key: str, value: str):
    """Persist an entry in the local store."""
    try:
        conn = _get_store()
        ts = datetime.now(timezone.utc).timestamp()
        conn.execute(
            "INSERT OR REPLACE INTO _result_cache (key, value, cached_at) VALUES (?,?,?)",
            (key, value, ts),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_latest_videos(limit: int = 20) -> list[dict]:
    """Return the most recent videos sorted by upload_date descending."""
    import json
    _key = f"latest:{limit}"
    _hit = _store_get(_key)
    if _hit:
        return json.loads(_hit)
    try:
        col = get_videos_collection()
        cursor = col.find(
            {},
            {"_id": 0, "title": 1, "channel_name": 1, "url": 1, "upload_date": 1},
        ).sort("upload_date", -1).limit(limit)
        result = list(cursor)
        _store_set(_key, json.dumps(result, default=str))
        return result
    except Exception:
        stale = _store_get(_key, allow_stale=True)
        if stale:
            return json.loads(stale)
        return []


def count_videos_by_channel(channel_name: str) -> int:
    """Count total videos stored for a given channel name (case-insensitive)."""
    _key = f"ch_count:{channel_name.lower()}"
    _hit = _store_get(_key)
    if _hit:
        return int(_hit)
    try:
        col = get_videos_collection()
        result = col.count_documents(
            {"channel_name": {"$regex": channel_name, "$options": "i"}}
        )
        _store_set(_key, str(result))
        return result
    except Exception:
        stale = _store_get(_key, allow_stale=True)
        return int(stale) if stale else 0


def count_videos_about_keyword(keyword: str, hours: int = 24) -> int:
    """Count videos mentioning a keyword in title or description within the last N hours."""
    _key = f"kw_count:{keyword.lower()}:{hours}"
    _hit = _store_get(_key)
    if _hit:
        return int(_hit)
    try:
        col = get_videos_collection()
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = {
            "$and": [
                {
                    "$or": [
                        {"title": {"$regex": keyword, "$options": "i"}},
                        {"description": {"$regex": keyword, "$options": "i"}},
                    ]
                },
                {"inserted_at": {"$gte": since}},
            ]
        }
        result = col.count_documents(query)
        _store_set(_key, str(result))
        return result
    except Exception:
        stale = _store_get(_key, allow_stale=True)
        return int(stale) if stale else 0


def get_videos_per_hour(hours: int = 24) -> list[dict]:
    """Aggregate video counts per hour for the last N hours."""
    import json
    _key = f"per_hour:{hours}"
    _hit = _store_get(_key)
    if _hit:
        return json.loads(_hit)
    try:
        col = get_videos_collection()
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        pipeline = [
            {"$match": {"inserted_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {"format": "%Y-%m-%d %H:00", "date": "$inserted_at"}
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        result = list(col.aggregate(pipeline))
        _store_set(_key, json.dumps(result, default=str))
        return result
    except Exception:
        stale = _store_get(_key, allow_stale=True)
        return json.loads(stale) if stale else []
