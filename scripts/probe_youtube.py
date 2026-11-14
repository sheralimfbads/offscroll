"""Display a small sample of public YouTube metadata; do not persist it."""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from offscroll.youtube import YouTubeError, fetch_most_popular


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region-code", default="US", help="Two-letter country code (default: US)")
    parser.add_argument(
        "--max-results", type=int, default=10, help="Number of videos, 1–50 (default: 10)"
    )
    args = parser.parse_args()

    # Resolve .env relative to this repository, even when run from another directory.
    # Existing environment variables take precedence over values in .env.
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    try:
        videos = fetch_most_popular(
            api_key=os.getenv("YOUTUBE_API_KEY", ""),
            region_code=args.region_code,
            max_results=args.max_results,
        )
    except YouTubeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not videos:
        print("No videos returned for this region.")
    for video in videos:
        print(f"Video ID: {video.id}")
        print(f"Title: {video.title}")
        print(f"Channel: {video.channel}")
        print(f"Published: {video.published_at}")
        print(f"Watch URL: {video.watch_url}")
        print(f"Embeddable: {'yes' if video.embeddable else 'no'}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
