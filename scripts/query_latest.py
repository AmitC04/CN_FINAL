"""Query latest videos from MongoDB and print to console."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.query_service import get_latest_videos


def main():
    """Print the latest stored videos."""
    videos = get_latest_videos(limit=20)

    if not videos:
        print("No videos found in the database.")
        return

    print(f"\n{'='*80}")
    print(f" Latest {len(videos)} Videos in Database")
    print(f"{'='*80}\n")

    for i, v in enumerate(videos, 1):
        print(f"{i:>3}. {v.get('title', 'N/A')}")
        print(f"     Channel : {v.get('channel_name', 'N/A')}")
        print(f"     URL     : {v.get('url', 'N/A')}")
        print(f"     Uploaded: {v.get('upload_date', 'N/A')}")
        print()


if __name__ == "__main__":
    main()
