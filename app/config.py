"""Configuration module — loads environment variables using python-dotenv."""

import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB
MONGO_URI: str = os.getenv("MONGO_URI", "")
MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "youtube_pipeline")

# YouTube
YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")
CHANNEL_IDS: list[str] = os.getenv("CHANNEL_IDS", "").split(",")
CHANNEL_HANDLES: list[str] = os.getenv("CHANNEL_HANDLES", "").split(",")

# Google / Gemini
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# API Security
API_KEY: str = os.getenv("API_KEY", "")

# Webhook
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
PUBSUB_HUB_URL: str = os.getenv("PUBSUB_HUB_URL", "https://pubsubhubbub.appspot.com/subscribe")
WEBHOOK_BASE_URL: str = os.getenv("WEBHOOK_BASE_URL", "http://localhost:8080")

# GCP
GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
GCP_REGION: str = os.getenv("GCP_REGION", "asia-south1")
