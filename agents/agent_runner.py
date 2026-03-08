"""Agent runner — Groq LLM with tool-calling for YouTube Intelligence."""

import os
import sys
import json
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from groq import Groq
from agents.agent_tools import (
    tool_count_videos_by_channel,
    tool_count_videos_about_keyword,
    tool_get_latest_videos,
    tool_get_videos_per_hour,
)

logger = logging.getLogger(__name__)

MODEL = "llama-3.3-70b-versatile"

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are a YouTube Intelligence assistant with access to a MongoDB database of YouTube video metadata.
You help users query information about YouTube videos from channels like @markets and @ANINewsIndia.
Always use the available tools to fetch real data. Be concise and helpful.
When showing video lists, format them nicely with title, channel, and URL.
When asked to plot or chart data, call tool_get_videos_per_hour and briefly summarize what the data shows (e.g. peak hour, total videos)."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "tool_count_videos_by_channel",
            "description": "Count total videos stored in the database for a given channel name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "Channel name e.g. 'markets' or 'ANINewsIndia'"
                    }
                },
                "required": ["channel_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_count_videos_about_keyword",
            "description": "Count videos mentioning a keyword in title/description within the last N hours.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Keyword to search for"},
                    "hours": {"type": "integer", "description": "Hours to look back, default 24"}
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_get_latest_videos",
            "description": "Return the latest N videos stored in the database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of videos to return, default 5"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tool_get_videos_per_hour",
            "description": "Get the number of videos published per hour for charting. Use when user asks for a plot or chart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "description": "Hours to look back, default 24"}
                },
                "required": []
            }
        }
    },
]

TOOL_MAP = {
    "tool_count_videos_by_channel": tool_count_videos_by_channel,
    "tool_count_videos_about_keyword": tool_count_videos_about_keyword,
    "tool_get_latest_videos": tool_get_latest_videos,
    "tool_get_videos_per_hour": tool_get_videos_per_hour,
}


def _call_tool(name: str, args: dict) -> str:
    """Dispatch a tool call by name."""
    fn = TOOL_MAP.get(name)
    if fn is None:
        return f"Unknown tool: {name}"
    try:
        return fn(**args)
    except Exception as exc:
        logger.error("Tool %s failed: %s", name, exc)
        return f"Tool error: {exc}"


def ask_agent_sync(query: str, session_id: str = "default") -> dict:
    """Send a query to Groq with tool-calling and return a structured result.

    Returns:
        dict with keys:
          - "text":       str — the LLM's final response text
          - "chart_data": list | None — hourly video counts for charting
          - "video_data": list | None — list of video dicts to render as cards
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    # First call — let model decide if it needs tools
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        max_tokens=2048,
    )

    msg = response.choices[0].message

    # If no tool calls, return directly
    if not msg.tool_calls:
        return {"text": msg.content or "No response.", "chart_data": None, "video_data": None}

    # Execute every tool call the model requested; track structured data
    chart_data = None
    video_data = None

    messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
        {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
        for tc in msg.tool_calls
    ]})

    for tc in msg.tool_calls:
        args = json.loads(tc.function.arguments)
        result = _call_tool(tc.function.name, args)

        # Capture raw structured data before it gets summarised by the LLM
        if tc.function.name == "tool_get_videos_per_hour":
            try:
                parsed = json.loads(result)
                if isinstance(parsed, list) and parsed and "_id" in parsed[0]:
                    chart_data = parsed
            except Exception:
                pass
        elif tc.function.name == "tool_get_latest_videos":
            try:
                parsed = json.loads(result)
                if isinstance(parsed, list) and parsed and "title" in parsed[0]:
                    video_data = parsed
            except Exception:
                pass

        messages.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": result,
        })

    # Second call — get the final answer with tool results
    final = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=2048,
    )
    text = final.choices[0].message.content or "Done."
    return {"text": text, "chart_data": chart_data, "video_data": video_data}


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Show latest 5 videos"
    print("Q:", q)
    res = ask_agent_sync(q)
    print("A:", res["text"])
    if res["chart_data"]:
        print("Chart data:", res["chart_data"])
    if res["video_data"]:
        print("Video data:", json.dumps(res["video_data"], indent=2, default=str))
