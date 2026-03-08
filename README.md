# YouTube Real-Time Ingestion Pipeline with Agentic AI Chatbot

A cloud-native system that monitors high-frequency YouTube channels in near real-time, stores metadata in MongoDB Atlas, and provides an Agentic AI chatbot powered by Google ADK + Gemini for natural-language querying.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        YOUTUBE PIPELINE                              │
│                                                                      │
│  ┌─────────────┐    ┌───────────────────┐    ┌──────────────────┐   │
│  │  YouTube     │───▶│ PubSubHubbub Hub  │───▶│  FastAPI Webhook │   │
│  │  Channels    │    └───────────────────┘    │  POST /webhook   │   │
│  │  @markets    │                             │  /youtube        │   │
│  │  @ANINews    │                             └────────┬─────────┘   │
│  └──────┬──────-┘                                      │             │
│         │                                              ▼             │
│         │ (historical)              ┌──────────────────────────┐     │
│         │                           │     YouTube Data API     │     │
│         ▼                           │         v3               │     │
│  ┌─────────────┐                    └────────────┬─────────────┘     │
│  │   yt-dlp    │                                 │                   │
│  │  (bulk      │                                 ▼                   │
│  │  ingestion) │──────────────────▶ ┌──────────────────────────┐     │
│  └─────────────┘                    │     MongoDB Atlas        │     │
│                                     │   (youtube_pipeline DB)  │     │
│                                     └────────────┬─────────────┘     │
│                                                  │                   │
│                              ┌───────────────────┤                   │
│                              │                   │                   │
│                              ▼                   ▼                   │
│                   ┌────────────────┐  ┌────────────────────┐        │
│                   │  FastAPI REST  │  │  Google ADK Agent  │        │
│                   │  GET /videos/  │  │  (Groq AI LLM)      │       │
│                   │  latest        │  └─────────┬──────────┘        │
│                   └────────────────┘            │                   │
│                                                  ▼                   │
│                                       ┌────────────────────┐        │
│                                       │  Streamlit Chatbot │        │
│                                       │  (User Interface)  │        │
│                                       └────────────────────┘        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
youtube_pipeline/
├── app/
│   ├── __init__.py
│   ├── config.py            # Environment variable loader
│   ├── database.py          # MongoDB Atlas connection
│   ├── models.py            # Pydantic schemas
│   ├── youtube_api.py       # YouTube Data API v3 client
│   ├── ingestion.py         # Video upsert logic
│   ├── webhook.py           # PubSubHubbub webhook router
│   ├── query_service.py     # MongoDB query helpers
│   └── main.py              # FastAPI application
├── agents/
│   ├── __init__.py
│   ├── agent_tools.py       # ADK tool functions
│   └── agent_runner.py      # Google ADK agent + Gemini runner
├── chatbot/
│   └── streamlit_app.py     # Streamlit chat UI
├── scripts/
│   ├── ingest_history.py    # Bulk historical ingestion via yt-dlp
│   ├── subscribe_webhook.py # Register PubSubHubbub subscriptions
│   └── query_latest.py      # CLI query for latest videos
├── .env.example
├── .gitignore
├── .dockerignore
├── cloudbuild.yaml          # Google Cloud Build config
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## Setup Instructions

### 1. Prerequisites

- Python 3.11+
- MongoDB Atlas cluster (free tier works)
- YouTube Data API v3 key
- Google AI (Gemini) API key
- yt-dlp installed (`pip install yt-dlp`)

### 2. Clone & Configure

```bash
git clone <repo-url>
cd youtube_pipeline

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your actual keys and connection strings
```

### 3. Historical Data Ingestion

Fetch the latest 1000 videos from each monitored channel:

```bash
python scripts/ingest_history.py
```

### 4. Start FastAPI Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### 5. Subscribe to Webhooks

After the server is publicly accessible (e.g., via ngrok or Cloud Run):

```bash
# Update WEBHOOK_BASE_URL in .env to your public URL first
python scripts/subscribe_webhook.py
```

### 6. Launch Chatbot

```bash
streamlit run chatbot/streamlit_app.py
```

---

## API Usage

### Health Check

```bash
curl http://localhost:8080/
```

### Get Latest Videos (requires API key)

```bash
curl -H "x-api-key: xK9mP2qL8nR4vT6w" http://localhost:8080/videos/latest
```

**Response:**

```json
[
  {
    "title": "Breaking: Market Update",
    "channel_name": "markets",
    "url": "https://www.youtube.com/watch?v=abc123",
    "upload_date": "2025-03-05T12:00:00Z"
  }
]
```

### Query Latest via CLI

```bash
python scripts/query_latest.py
```

---

## Deployment — Google Cloud Run

### Option A: gcloud CLI

```bash
# Build and deploy
gcloud run deploy youtube-pipeline \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars "MONGO_URI=<uri>,YOUTUBE_API_KEY=<key>,GOOGLE_API_KEY=<key>,API_KEY=<key>"
```

### Option B: Cloud Build

```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions "_MONGO_URI=<uri>,_MONGO_DB_NAME=youtube_pipeline,_YOUTUBE_API_KEY=<key>,_GOOGLE_API_KEY=<key>,_API_KEY=<key>,_WEBHOOK_SECRET=<secret>"
```

### Option C: Docker

```bash
docker build -t youtube-pipeline .
docker run -p 8080:8080 --env-file .env youtube-pipeline
```

---

## Chatbot — Example Queries

| Prompt | Expected Behavior |
|---|---|
| How many videos from markets channel have we saved in the database? | Calls `tool_count_videos_by_channel("markets")` → returns count |
| Give me a count of videos about USA in ANINewsIndia channel in the last 24 hours | Calls `tool_count_videos_about_keyword("USA", 24)` → returns count |
| Show latest 5 videos | Calls `tool_get_latest_videos(5)` → returns video list |
| Plot number of videos published per hour | Calls `tool_get_videos_per_hour(24)` → renders bar chart |

---

## Monitored Channels

| Handle | Channel ID |
|---|---|
| @markets | UCIALMKvObZNtJ6AmdCLP7Lg |
| @ANINewsIndia | UCtFQDgA8J8_iiwc5-KoAQlg |

---

## Tech Stack

| Component | Technology |
|---|---|
| API Framework | FastAPI |
| Database | MongoDB Atlas |
| Video Metadata | YouTube Data API v3 + yt-dlp |
| AI Agent | Google ADK + Gemini 1.5 Flash |
| Chat UI | Streamlit |
| Deployment | Google Cloud Run / Docker |
| Language | Python 3.12 |
