"""FastAPI application entry point."""

import logging
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import API_KEY
from app.webhook import router as webhook_router
from app.query_service import get_latest_videos
from app.models import VideoResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="YouTube Ingestion Pipeline",
    description="Real-time YouTube video ingestion and Agentic AI query system",
    version="1.0.0",
)

# --- API key security ---
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


async def verify_api_key(key: str = Security(api_key_header)):
    """Validate the x-api-key header."""
    if not key or key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key


# --- Routers ---
app.include_router(webhook_router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "youtube-pipeline"}


@app.get("/videos/latest", response_model=list[VideoResponse])
async def latest_videos(_key: str = Depends(verify_api_key)):
    """Return the 20 most recent videos sorted by upload_date descending."""
    return get_latest_videos(limit=20)
