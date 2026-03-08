"""PubSubHubbub webhook router for YouTube push notifications."""

import logging
import hmac
import hashlib
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Request, Response, Query

from app.config import WEBHOOK_SECRET
from app.ingestion import ingest_video_by_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])

ATOM_NS = "http://www.w3.org/2005/Atom"
YT_NS = "http://www.youtube.com/xml/schemas/2015"


@router.get("/youtube")
async def verify_subscription(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_topic: str = Query(None, alias="hub.topic"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Handle PubSubHubbub subscription verification (GET)."""
    logger.info("Subscription verification: mode=%s topic=%s", hub_mode, hub_topic)
    if hub_mode == "subscribe" and hub_challenge:
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=400)


@router.post("/youtube")
async def receive_notification(request: Request):
    """Receive a push notification from YouTube via PubSubHubbub (POST)."""
    body = await request.body()

    # Verify HMAC signature if present
    signature = request.headers.get("X-Hub-Signature")
    if signature and WEBHOOK_SECRET:
        expected = "sha1=" + hmac.HMAC(
            WEBHOOK_SECRET.encode(), body, hashlib.sha1
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            logger.warning("Invalid webhook signature")
            return Response(content="Invalid signature", status_code=403)

    # Parse Atom XML feed
    try:
        root = ET.fromstring(body)
        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            video_id_el = entry.find(f"{{{YT_NS}}}videoId")
            if video_id_el is not None and video_id_el.text:
                video_id = video_id_el.text.strip()
                logger.info("Webhook received video_id=%s", video_id)
                ingest_video_by_id(video_id)
    except ET.ParseError as exc:
        logger.error("Failed to parse webhook XML: %s", exc)
        return Response(content="Bad XML", status_code=400)

    return Response(content="OK", status_code=200)
