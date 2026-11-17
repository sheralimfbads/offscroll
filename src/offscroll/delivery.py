"""Finite public presentation, with no copied YouTube metadata or Gemini output."""

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import Engine

from offscroll.digests import LANES, read_digest
from offscroll.ranking import DigestError

PACKAGE = Path(__file__).parent


def safe_link(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parts = urlsplit(value)
        if (
            parts.scheme in {"http", "https"}
            and parts.hostname
            and not parts.username
            and not parts.password
        ):
            return value
    except ValueError:
        pass
    return None


def public_lanes(lanes: dict[str, list[dict[str, object]]]) -> dict[str, list[dict[str, object]]]:
    """Allowlist publication fields; static archives cannot enforce later deletion."""
    result: dict[str, list[dict[str, object]]] = {}
    for lane in LANES:
        entries = []
        for row in lanes[lane]:
            if lane == "youtube":
                # IDs/links only even on day one: CDN copies cannot be reliably expired.
                entries.append(
                    {
                        "lane_rank": row["lane_rank"],
                        "video_id": row["video_id"],
                        "url": "https://www.youtube.com/watch?v=" + str(row["video_id"]),
                    }
                )
                continue
            entry = {
                key: row.get(key) for key in ("lane_rank", "title", "domain", "why_here", "metrics")
            }
            entry["url"] = safe_link(row.get("url"))
            entry["discussion_url"] = safe_link(row.get("discussion_url"))
            entry["summary_label"] = "Source context"
            entry["summary"] = (
                "Follow the original story and Hacker News discussion for context."
                if lane == "hackernews"
                else "Open the Wikipedia article for background and its cited sources."
            )
            covered = row.get("also_covered_by", [])
            entry["also_covered_by"] = (
                [
                    {
                        "source": item.get("source"),
                        "title": item.get("title"),
                        "url": safe_link(item.get("url")),
                    }
                    for item in covered
                    if isinstance(item, dict) and item.get("source") in {"hackernews", "wikipedia"}
                ]
                if isinstance(covered, list)
                else []
            )
            entries.append(entry)
        result[lane] = entries
    return result


def render_page(
    lanes: dict[str, list[dict[str, object]]], *, date: str, asset_prefix: str = ""
) -> str:
    env = Environment(
        loader=FileSystemLoader(PACKAGE / "templates"), autoescape=select_autoescape(["html"])
    )
    return env.get_template("index.html").render(
        lanes=lanes,
        labels=LANES,
        date=date,
        count=sum(map(len, lanes.values())),
        assets=asset_prefix,
    )


def _write_atomic(path: Path, data: str | bytes) -> None:
    # Never follow existing output symlinks or overwrite an arbitrary directory.
    if path.is_symlink():
        raise DigestError("Export output must not contain symlinks.")
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temp_path = Path(temporary.name)
        try:
            temporary.write(data.encode() if isinstance(data, str) else data)
            temporary.flush()
            os.fchmod(temporary.fileno(), 0o644)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
    os.replace(temp_path, path)


def export_site(engine: Engine, output: Path = Path("site")) -> Path:
    if output.is_symlink() or output.resolve() == Path.cwd().resolve():
        raise DigestError("Choose a dedicated non-symlink export directory.")
    lanes = public_lanes(read_digest(engine))
    now = datetime.now(UTC)
    output.mkdir(parents=True, exist_ok=True)
    allowed = {"index.html", "digest.json", "style.css", ".nojekyll", "youtube-logo.png"}
    if any(path.name not in allowed for path in output.iterdir()):
        raise DigestError("Export directory contains unrelated files; choose an empty directory.")
    _write_atomic(
        output / "digest.json",
        json.dumps({"exported_at": now.isoformat(), "lanes": lanes}, ensure_ascii=True),
    )
    for asset in (PACKAGE / "static").iterdir():
        _write_atomic(output / asset.name, asset.read_bytes())
    _write_atomic(output / ".nojekyll", "")
    _write_atomic(output / "index.html", render_page(lanes, date=now.strftime("%d %B %Y")))
    return output / "index.html"
