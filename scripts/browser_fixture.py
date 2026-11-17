"""Serve synthetic, offline browser fixtures; never touch the owner's site or DB."""

import json
import shutil
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from offscroll.delivery import PACKAGE, public_lanes, render_page

output = Path(".browser-site")
output.mkdir(exist_ok=True)
lanes = {
    "hackernews": [
        {
            "lane_rank": number,
            "title": title,
            "url": f"https://example.org/story-{number}",
            "domain": "example.org",
            "discussion_url": f"https://news.ycombinator.com/item?id={number}",
            "why_here": "Readers are discussing this story on Hacker News.",
        }
        for number, title in enumerate(
            [
                "What happens when we make more room for curiosity?",
                "A small, useful idea for the open web",
                "Designing technology that respects your attention",
                "The quiet value of understanding how things work",
                "Building a better reading habit, one day at a time",
                "An independent project with a thoughtful approach",
            ],
            1,
        )
    ],
    "wikipedia": [
        {
            "lane_rank": number,
            "title": title,
            "url": f"https://en.wikipedia.org/wiki/Example_{number}",
            "domain": "en.wikipedia.org",
            "why_here": "More readers are exploring this topic on Wikipedia.",
        }
        for number, title in enumerate(
            [
                "The history of public libraries",
                "The night sky",
                "Open knowledge",
                "The architecture of everyday places",
                "Ways of seeing the world",
            ],
            1,
        )
    ],
    "youtube": [{"lane_rank": number, "video_id": str(number) * 11} for number in range(1, 5)],
}
for name, data in [("index.html", lanes), ("empty.html", {key: [] for key in lanes})]:
    (output / name).write_text(
        render_page(
            public_lanes(data), date="17 November 2026", generated_at="2026-11-17T02:17:00+00:00"
        )
    )
for asset in (PACKAGE / "static").iterdir():
    shutil.copyfile(asset, output / asset.name)
(output / "digest.json").write_text(json.dumps(public_lanes(lanes)))
handler = partial(SimpleHTTPRequestHandler, directory=str(output))
# Loopback-only fixture server, not a production service.
ThreadingHTTPServer(("127.0.0.1", 8765), handler).serve_forever()
