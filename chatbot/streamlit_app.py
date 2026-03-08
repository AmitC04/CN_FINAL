"""YouTube Intelligence Chatbot — Streamlit UI with Groq LLM backend."""

import os
import sys
import json
import uuid
import concurrent.futures
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import plotly.graph_objects as go

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from agents.agent_runner import ask_agent_sync
from app.database import get_videos_collection, is_using_mock

logger = logging.getLogger(__name__)


@st.cache_resource(show_spinner=False)
def _ensure_data_loaded():
    """On first run, if DB is empty (or mock mode), ingest the latest videos from yt-dlp."""
    try:
        col = get_videos_collection()
        if col.count_documents({}) == 0:
            logger.info("DB empty — auto-ingesting latest videos via yt-dlp...")
            from scripts.ingest_history import ingest_channel
            from app.config import CHANNEL_HANDLES, CHANNEL_IDS
            for handle, cid in zip(CHANNEL_HANDLES, CHANNEL_IDS):
                ingest_channel(f"https://www.youtube.com/{handle}/videos", cid, max_videos=50)
            return f"Ingested from yt-dlp. Total docs: {col.count_documents({})}"
        return f"DB has {col.count_documents({})} docs."
    except Exception as e:
        return f"DB init skipped: {e}"


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_sidebar_stats():
    """Fetch DB stats — works for both Atlas and in-memory mock."""
    try:
        from app.query_service import count_videos_by_channel, get_latest_videos
        m = count_videos_by_channel("markets")
        a = count_videos_by_channel("ANINewsIndia")
        latest = get_latest_videos(1)
        last = str(latest[0].get("upload_date", "—"))[:10] if latest else "—"
        return m, a, last
    except Exception:
        return None, None, None

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="YouTube Intelligence Chatbot",
    page_icon="▶",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Trigger data load once (blocks until yt-dlp finishes first time)
with st.spinner("⏳ Loading data…"):
    _db_status = _ensure_data_loaded()

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  html, body, [data-testid="stApp"] {
    background-color: #0a0a0a;
    color: #f1f1f1;
    font-family: 'Inter', 'Segoe UI', sans-serif;
  }
  #MainMenu, footer, header { visibility: hidden; }

  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #111111 0%, #0d0d0d 100%) !important;
    border-right: 1px solid #1e1e1e;
  }
  [data-testid="stSidebar"] * { color: #f1f1f1 !important; }
  [data-testid="stSidebar"] button {
    background: #181818 !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 10px !important;
    color: #bbb !important;
    text-align: left !important;
    font-size: 0.82rem !important;
    transition: all 0.2s ease !important;
    padding: 8px 12px !important;
  }
  [data-testid="stSidebar"] button:hover {
    border-color: #ff0000 !important;
    color: #fff !important;
    background: #1e0000 !important;
    transform: translateX(3px) !important;
  }

  .main .block-container { padding: 2rem 3rem 6rem 3rem; max-width: 900px; margin: auto; }

  /* ── Header ── */
  .yt-header {
    display: flex; align-items: center; gap: 16px;
    padding-bottom: 16px;
    border-bottom: 2px solid #ff0000;
    margin-bottom: 4px;
  }
  .yt-logo {
    background: linear-gradient(135deg, #ff0000, #cc0000);
    color: white; font-weight: 900;
    font-size: 1.2rem; padding: 6px 14px; border-radius: 10px;
    letter-spacing: 1px; box-shadow: 0 2px 12px rgba(255,0,0,0.35);
  }
  .yt-header-text { font-size: 1.8rem; font-weight: 800; color: #fff; letter-spacing: -0.5px; }
  .yt-subtitle { color: #666; font-size: 0.86rem; margin-bottom: 24px; margin-top: 2px; }

  /* ── Chat bubbles ── */
  .msg-wrap { margin-bottom: 20px; }
  .msg-user { display: flex; justify-content: flex-end; gap: 10px; align-items: flex-end; }
  .msg-bot  { display: flex; justify-content: flex-start; gap: 10px; align-items: flex-end; }

  .av {
    width: 34px; height: 34px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.95rem; flex-shrink: 0;
  }
  .av-user { background: linear-gradient(135deg, #ff0000, #cc0000); box-shadow: 0 2px 8px rgba(255,0,0,0.3); }
  .av-bot  { background: #1a1a1a; border: 1.5px solid #333; }

  .bub {
    max-width: 74%; padding: 12px 16px; border-radius: 18px;
    font-size: 0.91rem; line-height: 1.7;
    white-space: pre-wrap; word-break: break-word;
  }
  .bub-user {
    background: linear-gradient(135deg, #cc0000, #990000);
    color: #fff; border-bottom-right-radius: 4px;
    box-shadow: 0 2px 10px rgba(204,0,0,0.25);
  }
  .bub-bot {
    background: #161616; color: #e8e8e8;
    border-bottom-left-radius: 4px;
    border: 1px solid #252525;
    box-shadow: 0 1px 6px rgba(0,0,0,0.4);
  }

  /* ── Video Cards ── */
  .vcard {
    background: linear-gradient(135deg, #141414, #131313);
    border: 1px solid #252525;
    border-left: 3px solid #ff0000;
    border-radius: 12px; padding: 14px 18px; margin: 6px 0;
    transition: border-color 0.2s, transform 0.2s;
  }
  .vcard:hover { border-color: #ff3333; transform: translateX(2px); }
  .vcard-num  { color: #ff4444; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; }
  .vcard-title { font-weight: 600; font-size: 0.93rem; color: #fff; margin-top: 3px; }
  .vcard-meta  { color: #666; font-size: 0.77rem; margin-top: 6px; display: flex; gap: 12px; flex-wrap: wrap; }
  .vcard-meta span { display: flex; align-items: center; gap: 4px; }
  .vcard-link { margin-top: 8px; }
  .vcard-link a { color: #ff5555; text-decoration: none; font-size: 0.8rem; font-weight: 500;
    padding: 3px 8px; border: 1px solid #ff3333; border-radius: 6px;
    transition: background 0.2s; }
  .vcard-link a:hover { background: rgba(255,0,0,0.12); }

  /* ── Stat chips ── */
  .stat-chip {
    display: inline-flex; align-items: center; gap: 6px;
    background: #161616; border: 1px solid #252525;
    border-radius: 8px; padding: 6px 12px;
    font-size: 0.82rem; color: #ccc; margin: 3px 2px;
  }
  .stat-chip-val { color: #ff4444; font-weight: 700; font-size: 0.9rem; }

  /* ── Section badge ── */
  .section-badge {
    display: inline-block; background: rgba(255,0,0,0.12);
    color: #ff5555; font-size: 0.72rem; font-weight: 600;
    padding: 2px 8px; border-radius: 5px; border: 1px solid rgba(255,0,0,0.2);
    margin-bottom: 8px; letter-spacing: 0.5px; text-transform: uppercase;
  }

  /* ── Empty state ── */
  .empty-state { text-align: center; padding: 72px 20px; color: #333; }
  .empty-state .big-icon { font-size: 4rem; }
  .empty-state .hint { font-size: 1.05rem; margin-top: 12px; color: #444; font-weight: 500; }
  .empty-state .sub  { font-size: 0.82rem; margin-top: 6px; color: #2e2e2e; }
  .empty-state .pills { margin-top: 16px; }
  .pill {
    display: inline-block; background: #161616; border: 1px solid #2a2a2a;
    color: #555; border-radius: 20px; padding: 4px 12px;
    font-size: 0.78rem; margin: 3px;
  }

  /* ── Chat input ── */
  [data-testid="stChatInput"] { background: #0a0a0a !important; }
  [data-testid="stChatInput"] textarea {
    background: #141414 !important;
    color: #eee !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 16px !important;
    font-size: 0.92rem !important;
    font-family: 'Inter', 'Segoe UI', sans-serif !important;
  }
  [data-testid="stChatInput"] textarea:focus {
    border-color: #ff0000 !important;
    box-shadow: 0 0 0 2px rgba(255,0,0,0.12) !important;
  }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: #0a0a0a; }
  ::-webkit-scrollbar-thumb { background: #2a2a2a; border-radius: 4px; }
  ::-webkit-scrollbar-thumb:hover { background: #ff0000; }

  /* ── Plotly container ── */
  .js-plotly-plot { border-radius: 12px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)



# ─── Helper functions ─────────────────────────────────────────────────────────

def render_chart(data: list[dict]):
    """Render an interactive Plotly bar chart."""
    hours  = [str(d["_id"]) for d in data]
    counts = [d["count"] for d in data]
    total  = sum(counts)
    peak   = max(counts) if counts else 0

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=hours,
        y=counts,
        marker=dict(
            color=counts,
            colorscale=[[0, "#4a0000"], [0.5, "#cc0000"], [1, "#ff4444"]],
            line=dict(color="rgba(255,0,0,0.4)", width=1),
        ),
        text=counts,
        textposition="outside",
        textfont=dict(color="#ccc", size=11),
        hovertemplate="<b>Hour %{x}</b><br>Videos: %{y}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text=f"📊 Videos Published Per Hour  ·  <span style='color:#ff4444'>{total} total</span>  ·  Peak: <span style='color:#ff4444'>{peak}</span>",
            font=dict(color="#e0e0e0", size=14),
            x=0,
        ),
        paper_bgcolor="#111111",
        plot_bgcolor="#0d0d0d",
        font=dict(color="#999", family="Inter, Segoe UI, sans-serif"),
        xaxis=dict(
            title="Hour (UTC)",
            color="#555",
            gridcolor="#1a1a1a",
            tickfont=dict(size=11),
            showline=False,
        ),
        yaxis=dict(
            title="Video Count",
            color="#555",
            gridcolor="#1a1a1a",
            zeroline=False,
            tickfont=dict(size=11),
        ),
        height=340,
        margin=dict(l=10, r=10, t=50, b=10),
        bargap=0.25,
        hoverlabel=dict(bgcolor="#1e1e1e", bordercolor="#ff0000", font_color="#fff"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def try_chart(text: str) -> list[dict] | None:
    try:
        d = json.loads(text)
        if isinstance(d, list) and d and "_id" in d[0] and "count" in d[0]:
            return d
    except Exception:
        pass
    return None


def try_videos(text: str) -> list[dict] | None:
    try:
        d = json.loads(text)
        if isinstance(d, list) and d and "title" in d[0]:
            return d
    except Exception:
        pass
    return None


def render_video_cards(videos: list[dict]):
    for i, v in enumerate(videos, 1):
        date = str(v.get("upload_date", ""))[:10]
        channel = v.get("channel_name", "—")
        title   = v.get("title", "N/A")
        url     = v.get("url", "#")
        st.markdown(f"""
        <div class="vcard">
          <div class="vcard-num">#{i}</div>
          <div class="vcard-title">{title}</div>
          <div class="vcard-meta">
            <span>📺 {channel}</span>
            <span>📅 {date}</span>
          </div>
          <div class="vcard-link"><a href="{url}" target="_blank">▶ Watch on YouTube ↗</a></div>
        </div>""", unsafe_allow_html=True)


def render_message(role, content, chart_data=None, video_data=None):
    """Render one chat message."""
    if role == "user":
        st.markdown(f"""
        <div class="msg-wrap">
          <div class="msg-user">
            <div class="bub bub-user">{content}</div>
            <div class="av av-user">👤</div>
          </div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="msg-wrap">
          <div class="msg-bot">
            <div class="av av-bot">🤖</div>
            <div class="bub bub-bot">{content}</div>
          </div>
        </div>""", unsafe_allow_html=True)
        if chart_data:
            render_chart(chart_data)
        if video_data:
            st.markdown('<div class="section-badge">Results</div>', unsafe_allow_html=True)
            render_video_cards(video_data)


# ─── Session state ────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "quick_prompt" not in st.session_state:
    st.session_state.quick_prompt = None


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;padding-bottom:12px;border-bottom:1px solid #1e1e1e;margin-bottom:12px">
      <div style="background:linear-gradient(135deg,#ff0000,#cc0000);color:white;font-weight:900;font-size:1rem;padding:4px 10px;border-radius:8px;box-shadow:0 2px 8px rgba(255,0,0,0.3)">▶ YT</div>
      <div style="font-size:1rem;font-weight:700;color:#fff">YouTube Intelligence</div>
    </div>
    <div style="color:#555;font-size:0.78rem;margin-bottom:16px">Real-time channel monitoring &amp; AI query</div>
    """, unsafe_allow_html=True)

    # ── Live Stats (non-blocking) ────────────────────────────────────────
    st.markdown("#### 📊 Live Database Stats")
    markets_count, ani_count, last_date = _fetch_sidebar_stats()
    if markets_count is not None:
        col1, col2 = st.columns(2)
        col1.metric("@markets", f"{markets_count:,}")
        col2.metric("@ANINews", f"{ani_count:,}")
        st.caption(f"🕐 Latest: **{last_date}**")
    else:
        st.caption("⚠️ DB stats unavailable")

    st.markdown("---")

    # ── Quick Prompts ───────────────────────────────────────────────────
    st.markdown("#### 💡 Quick Prompts")
    PROMPTS = [
        "How many videos from markets channel?",
        "Videos about USA in ANINewsIndia (24h)",
        "Show latest 5 videos",
        "Plot videos published per hour",
        "How many videos about India today?",
    ]
    for p in PROMPTS:
        if st.button(p, key=f"qp_{p}", use_container_width=True):
            st.session_state.quick_prompt = p
            st.rerun()

    st.markdown("---")

    # ── Channels ────────────────────────────────────────────────────────
    st.markdown("#### 📡 Monitored Channels")
    st.markdown("""
    <div style="display:flex;flex-direction:column;gap:6px;margin-top:6px">
      <div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;padding:8px 12px;font-size:0.82rem">
        <span style="color:#ff4444;font-weight:700">@markets</span>
        <span style="color:#555;font-size:0.75rem;margin-left:6px">Bloomberg Markets</span>
      </div>
      <div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;padding:8px 12px;font-size:0.82rem">
        <span style="color:#ff4444;font-weight:700">@ANINewsIndia</span>
        <span style="color:#555;font-size:0.75rem;margin-left:6px">ANI News India</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Tech Stack ──────────────────────────────────────────────────────
    st.markdown("#### ⚙️ Tech Stack")
    stack_items = [
        ("🟩", "Groq · Llama 3.3 70B"),
        ("🍃", "MongoDB Atlas"),
        ("📺", "YouTube API v3"),
        ("⚡", "FastAPI + Streamlit"),
    ]
    for icon, label in stack_items:
        st.markdown(f"<div style='font-size:0.8rem;color:#666;padding:2px 0'>{icon} {label}</div>", unsafe_allow_html=True)

    st.markdown("---")

    # ── Session info + Clear ─────────────────────────────────────────────
    msg_count = len(st.session_state.get("messages", []))
    if msg_count > 0:
        st.caption(f"💬 {msg_count} messages in this session")
    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()


# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="yt-header">
  <div class="yt-logo">▶ YT</div>
  <div class="yt-header-text">YouTube Intelligence</div>
</div>
<div class="yt-subtitle">Ask natural-language questions about live YouTube data</div>
""", unsafe_allow_html=True)


# ─── Chat history ─────────────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown("""
    <div class="empty-state">
      <div class="hint">Start a conversation</div>
      <div class="sub">Use the quick prompts on the left or type your question below</div>
      <div class="pills" style="margin-top:20px">
        <span class="pill">📊 Charts</span>
        <span class="pill">📺 Video Lists</span>
        <span class="pill">🔍 Keyword Search</span>
        <span class="pill">📈 Channel Stats</span>
      </div>
    </div>""", unsafe_allow_html=True)
else:
    for msg in st.session_state.messages:
        render_message(
            msg["role"],
            msg["content"],
            chart_data=msg.get("chart_data"),
            video_data=msg.get("video_data"),
        )


# ─── Input ────────────────────────────────────────────────────────────────────
user_input = st.chat_input("Ask me about YouTube videos…")

# Override with sidebar quick-prompt if clicked
if st.session_state.quick_prompt:
    user_input = st.session_state.quick_prompt
    st.session_state.quick_prompt = None

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.spinner("🤖 Thinking — querying database & generating response…"):
        try:
            raw = ask_agent_sync(user_input, st.session_state.session_id)
        except Exception as e:
            raw = f"⚠️ Error: {e}"

    chart_data = try_chart(raw)
    video_data = try_videos(raw) if not chart_data else None

    if chart_data:
        display = "Here is the hourly video distribution:"
    elif video_data:
        display = f"Here are the latest {len(video_data)} videos:"
    else:
        display = raw

    st.session_state.messages.append({
        "role": "assistant",
        "content": display,
        "chart_data": chart_data,
        "video_data": video_data,
    })
    st.rerun()

