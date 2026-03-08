"""Subscribe to YouTube PubSubHubbub notifications for monitored channels."""

import os
import sys
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import requests
from app.config import CHANNEL_IDS, PUBSUB_HUB_URL, WEBHOOK_BASE_URL, WEBHOOK_SECRET

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TOPIC_URL_TEMPLATE = "https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}"


def subscribe(channel_id: str, mode: str = "subscribe"):
    """Send a subscription request to Google PubSubHubbub hub.

    Args:
        channel_id: YouTube channel ID to subscribe to.
        mode: 'subscribe' or 'unsubscribe'.
    """
    callback_url = f"{WEBHOOK_BASE_URL}/webhook/youtube"
    topic_url = TOPIC_URL_TEMPLATE.format(channel_id=channel_id)

    data = {
        "hub.callback": callback_url,
        "hub.topic": topic_url,
        "hub.verify": "async",
        "hub.mode": mode,
        "hub.verify_token": WEBHOOK_SECRET,
        "hub.lease_seconds": "864000",  # 10 days
    }

    logger.info("Subscribing to channel %s ...", channel_id)
    resp = requests.post(PUBSUB_HUB_URL, data=data, timeout=30)

    if resp.status_code == 202:
        logger.info("Subscription request accepted for channel %s", channel_id)
    else:
        logger.error(
            "Subscription failed for channel %s: %s %s",
            channel_id, resp.status_code, resp.text[:200],
        )


def main():
    """Subscribe to PubSubHubbub for all configured channels."""
    for channel_id in CHANNEL_IDS:
        channel_id = channel_id.strip()
        if channel_id:
            subscribe(channel_id)
    logger.info("All subscription requests sent.")


if __name__ == "__main__":
    main()
