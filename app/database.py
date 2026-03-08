"""MongoDB Atlas connection manager — falls back to in-memory mongomock when Atlas port 27017 is unreachable."""

import logging
import socket

from pymongo.collection import Collection

from app.config import MONGO_URI, MONGO_DB_NAME

logger = logging.getLogger(__name__)

_client = None
_using_mock = False


def _atlas_reachable() -> bool:
    """Quick 3-second TCP probe to see if port 27017 is open."""
    try:
        import re
        # Extract hostname from SRV URI like mongodb+srv://user:pass@cluster.mongodb.net/
        host = re.search(r"@([^/]+)", MONGO_URI)
        if not host:
            return False
        # SRV resolves to shard hostnames — probe the first one directly
        import dns.resolver
        srv = dns.resolver.resolve(f"_mongodb._tcp.{host.group(1)}", "SRV")
        target = str(list(srv)[0].target).rstrip(".")
        s = socket.create_connection((target, 27017), timeout=3)
        s.close()
        return True
    except Exception:
        return False


def get_client():
    """Return a real MongoClient or a mongomock client if Atlas is unreachable."""
    global _client, _using_mock
    if _client is not None:
        return _client

    if _atlas_reachable():
        from pymongo import MongoClient
        _client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=15000,
            connectTimeoutMS=10000,
            socketTimeoutMS=15000,
        )
        _using_mock = False
        logger.info("Connected to MongoDB Atlas.")
    else:
        import mongomock
        _client = mongomock.MongoClient()
        _using_mock = True
        logger.warning("Atlas unreachable — using in-memory mongomock database.")

    return _client


def get_database():
    """Return the configured database."""
    return get_client()[MONGO_DB_NAME]


def get_videos_collection() -> Collection:
    """Return the 'videos' collection, creating indexes only on real Atlas."""
    db = get_database()
    col = db["videos"]
    if not _using_mock:
        col.create_index("video_id", unique=True)
        col.create_index("upload_date")
        col.create_index("channel_name")
    return col


def is_using_mock() -> bool:
    """Return True if running against the in-memory fallback."""
    return _using_mock
