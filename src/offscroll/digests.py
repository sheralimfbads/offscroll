"""Build and read atomic, replaceable digests with strictly separate source lanes."""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Connection, Engine, RowMapping, bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from offscroll.ranking import (
    Candidate,
    DigestError,
    Ranked,
    Window,
    digest_window,
    load_ranking,
    rank_candidates,
    select_lanes,
)
from offscroll.retention import purge_expired
from offscroll.summaries import Summarizer, cache_key, configured_summarizer

LANES = {"hackernews": "Hacker News", "wikipedia": "Wikipedia", "youtube": "YouTube"}

# The ratio exists only in ORDER BY. It is never returned to Python, stored,
# normalized, combined with another source, or included in presentation data.
YOUTUBE_CANDIDATES = text("""
    SELECT id, external_id, metadata->>'channel_id' AS channel_id
    FROM marts.latest_item_metrics
    WHERE source = 'youtube'
      AND published_at >= :start AND published_at < :end AND published_at <= :now
      AND published_at >= :now - interval '7 days'
      AND captured_at > :now - interval '30 days' AND captured_at <= :now
      AND last_seen_at > :now - interval '30 days' AND last_seen_at <= :now
      AND metadata->>'privacy_status' = 'public'
      AND metadata->'embeddable' = 'true'::jsonb
      AND metadata->>'channel_id' IS NOT NULL AND views IS NOT NULL
    ORDER BY views / greatest(extract(epoch FROM (:now - published_at)) / 86400.0, 1) DESC,
             published_at DESC, external_id
""")

INSERT_DIGEST_ITEM = text("""
    INSERT INTO core.digest_items
        (digest_id, lane, lane_rank, item_id, final_score, score_breakdown,
         cluster, content, summary_id)
    VALUES (:digest_id, :lane, :lane_rank, :item_id, :final_score, :breakdown,
            :cluster, :content, :summary_id)
""").bindparams(*(bindparam(key, type_=JSONB) for key in ("breakdown", "cluster", "content")))


def shared_candidates(connection: Connection, window: Window, now: datetime) -> list[Candidate]:
    rows = connection.execute(
        text("""
        SELECT * FROM marts.latest_item_metrics
        WHERE captured_at <= :now AND last_seen_at <= :now AND (
            (source = 'hackernews' AND published_at >= :start AND published_at < :end)
            OR (source = 'wikipedia' AND published_at > :start AND published_at <= :end)
        ) AND published_at <= :now
    """),
        {"start": window.start, "end": window.end, "now": now},
    ).mappings()
    result = []
    for row in rows:
        spike = row["metadata"].get("spike_ratio")
        result.append(
            Candidate(
                item_id=row["id"],
                source=row["source"],
                external_id=row["external_id"],
                title=row["title"],
                url=row["url"],
                domain=row["domain"],
                published_at=row["published_at"],
                score=row["score"],
                comments=row["comments"],
                views=row["views"],
                spike_ratio=float(spike) if isinstance(spike, (int, float)) else None,
                discussion_url=row["discussion_url"],
                description=row["metadata"].get("source_description")
                if isinstance(row["metadata"].get("source_description"), str)
                else None,
            )
        )
    return result


def youtube_candidates(
    connection: Connection,
    window: Window,
    now: datetime,
    limit: int,
) -> list[RowMapping]:
    rows = connection.execute(
        YOUTUBE_CANDIDATES, {"start": window.start, "end": window.end, "now": now}
    ).mappings()
    selected = []
    channels = set()
    for row in rows:
        if row["channel_id"] in channels:
            continue
        selected.append(row)
        channels.add(row["channel_id"])
        if len(selected) == limit:
            break
    return selected


def _context(item: Candidate) -> dict[str, object]:
    return {
        "source": item.source,
        "external_id": item.external_id,
        "title": item.title,
        "url": item.url,
        "discussion_url": item.discussion_url,
        "domain": item.domain,
    }


def why_here(row: Ranked) -> str:
    item = row.item
    if item.source == "hackernews":
        reason = (
            f"Hacker News story with {item.score} points"
            if item.score is not None
            else "Hacker News story"
        )
    else:
        reason = (
            f"Wikipedia topic with {item.views} views over seven days"
            if item.views is not None
            else "Wikipedia topic"
        )
    sources = sorted({LANES[i.source] for i in row.also_covered})
    return reason + ("; also covered by " + ", ".join(sources) if sources else "") + "."


def _store_summary(
    connection: Connection, item: Candidate, summarizer: Summarizer, now: datetime
) -> int:
    key = cache_key(item, summarizer.model, summarizer.prompt_version)
    cached = connection.execute(
        text("SELECT id FROM core.item_summaries WHERE input_hash = :key"), {"key": key}
    ).scalar_one_or_none()
    if cached is not None:
        return int(cached)
    summary = summarizer.summarize(item)
    return int(
        connection.execute(
            text("""
        INSERT INTO core.item_summaries
            (item_id, source, summary, model, prompt_version, input_hash, input_tokens,
             output_tokens, cost_estimate, created_at)
        VALUES (:item_id, :source, :text, :model, :prompt_version, :input_hash,
                :input_tokens, :output_tokens, :cost_estimate, :now)
        ON CONFLICT (input_hash) DO UPDATE SET input_hash = EXCLUDED.input_hash
        RETURNING id
    """),
            {**asdict(summary), "item_id": item.item_id, "source": item.source, "now": now},
        ).scalar_one()
    )


def build_digest(
    engine: Engine,
    *,
    week: str | None = None,
    now: datetime | None = None,
    config_path: Path = Path("config/ranking.yaml"),
    summarizer: Summarizer | None = None,
) -> int:
    now = now or datetime.now(UTC)
    window = digest_window(now, week)
    config = load_ranking(config_path)
    summarizer = summarizer or configured_summarizer(engine)
    purge_expired(engine)
    # The unique window upsert takes a row lock: concurrent replacements serialize.
    with engine.begin() as connection:
        digest_id = int(
            connection.execute(
                text("""
            INSERT INTO core.digests
                (week_start, week_end, window_kind, generated_at, config_snapshot)
            VALUES (:start, :end, :kind, :now, :config)
            ON CONFLICT (week_start, week_end, window_kind) DO UPDATE SET
                generated_at = EXCLUDED.generated_at, config_snapshot = EXCLUDED.config_snapshot
            RETURNING id
        """).bindparams(bindparam("config", type_=JSONB)),
                {
                    "start": window.start.date(),
                    "end": window.end.date(),
                    "kind": "iso_week" if week else "rolling",
                    "now": now,
                    "config": {
                        "ranking": config.model_dump(),
                        "window_start": window.start.isoformat(),
                        "window_end": window.end.isoformat(),
                        "mode": "iso_week" if week else "rolling",
                        "summarizer": summarizer.model,
                        "version": 1,
                    },
                },
            ).scalar_one()
        )
        connection.execute(
            text("DELETE FROM core.digest_items WHERE digest_id = :id"), {"id": digest_id}
        )
        lanes = select_lanes(
            rank_candidates(shared_candidates(connection, window, now), config), config
        )
        for lane, entries in lanes.items():
            for rank, row in enumerate(entries, 1):
                item = row.item
                content = {
                    **_context(item),
                    "why_here": why_here(row),
                    "metrics": {
                        "score": item.score,
                        "comments": item.comments,
                        "views": item.views,
                    },
                }
                connection.execute(
                    INSERT_DIGEST_ITEM,
                    {
                        "digest_id": digest_id,
                        "lane": lane,
                        "lane_rank": rank,
                        "item_id": item.item_id,
                        "final_score": row.final_score,
                        "breakdown": row.breakdown,
                        "cluster": [_context(i) for i in row.also_covered],
                        "content": content,
                        "summary_id": _store_summary(connection, item, summarizer, now),
                    },
                )
        for rank, video in enumerate(
            youtube_candidates(connection, window, now, config.youtube_slots), 1
        ):
            connection.execute(
                INSERT_DIGEST_ITEM,
                {
                    "digest_id": digest_id,
                    "lane": "youtube",
                    "lane_rank": rank,
                    "item_id": video["id"],
                    "final_score": None,
                    "breakdown": {},
                    "cluster": [],
                    "summary_id": None,
                    "content": {
                        "video_id": video["external_id"],
                        "url": "https://www.youtube.com/watch?v=" + video["external_id"],
                    },
                },
            )
    return digest_id


def read_digest(
    engine: Engine,
    *,
    week: str | None = None,
    now: datetime | None = None,
    explain: bool = False,
    purge: bool = True,
) -> dict[str, list[dict[str, object]]]:
    now = now or datetime.now(UTC)
    window = digest_window(now, week) if week else None
    if purge:
        purge_expired(engine)
    with engine.connect() as connection:
        if window:
            digest_id = connection.execute(
                text("""
                SELECT id FROM core.digests WHERE week_start = :start AND week_end = :end
                  AND window_kind = 'iso_week'
            """),
                {"start": window.start.date(), "end": window.end.date()},
            ).scalar_one_or_none()
        else:
            digest_id = connection.execute(
                text("SELECT id FROM core.digests ORDER BY generated_at DESC, id DESC LIMIT 1")
            ).scalar_one_or_none()
        if digest_id is None:
            raise DigestError("No digest found. Run offscroll build-digest first.")
        rows = connection.execute(
            text("""
            SELECT di.*, s.summary, s.model FROM core.digest_items di
            LEFT JOIN core.item_summaries s ON s.id = di.summary_id
            WHERE digest_id = :id ORDER BY lane, lane_rank
        """),
            {"id": digest_id},
        ).mappings()
        lanes: dict[str, list[dict[str, object]]] = {lane: [] for lane in LANES}
        for row in rows:
            entry: dict[str, object] = {"lane_rank": row["lane_rank"], **row["content"]}
            if row["lane"] == "youtube":
                # No historical copy. Read current API fields only while the digest
                # and both the item and its metric observation are younger than 30 days.
                current = (
                    connection.execute(
                        text("""
                    SELECT m.title, m.views, m.likes, m.comments,
                           m.metadata->'thumbnails' AS thumbnails
                    FROM marts.latest_item_metrics m JOIN core.digests d ON d.id = :digest_id
                    WHERE m.id = :item_id AND m.source = 'youtube'
                      AND m.external_id = :video_id
                      AND m.metadata->>'privacy_status' = 'public'
                      AND m.metadata->'embeddable' = 'true'::jsonb
                      AND d.generated_at > :now - interval '30 days'
                      AND m.last_seen_at > :now - interval '30 days' AND m.last_seen_at <= :now
                      AND m.captured_at > :now - interval '30 days' AND m.captured_at <= :now
                """),
                        {
                            "item_id": row["item_id"],
                            "digest_id": digest_id,
                            "now": now,
                            "video_id": row["content"]["video_id"],
                        },
                    )
                    .mappings()
                    .first()
                )
                if current:
                    entry.update(dict(current))
                # Never expose internal selection inputs, category labels or a score.
            else:
                entry.update(
                    {
                        "also_covered_by": row["cluster"],
                        "summary": row["summary"],
                        "summary_label": "Source context"
                        if row["model"] == "template"
                        else "AI-generated summary",
                    }
                )
                if explain:
                    entry.update(
                        {
                            "final_score": row["final_score"],
                            "score_breakdown": row["score_breakdown"],
                        }
                    )
            lanes[row["lane"]].append(entry)
        return lanes


def render_digest(lanes: dict[str, list[dict[str, object]]]) -> str:
    """CLI presentation: sections and lane ranks, JSON-escaped untrusted strings."""
    lines = []
    for lane, label in LANES.items():
        lines.append(label)
        lines.extend(json.dumps(entry, ensure_ascii=True) for entry in lanes[lane])
        if not lanes[lane]:
            lines.append("No eligible items.")
        lines.append("")
    lines.append("That's everything for this week")
    return "\n".join(lines)


def summary_review_inputs(engine: Engine) -> list[dict[str, object]]:
    """Local-only review manifest; approval is never inferred from source publicity."""
    from offscroll.summaries import approval_hash, public_input

    now = datetime.now(UTC)
    with engine.connect() as connection:
        candidates = shared_candidates(connection, digest_window(now), now)
    return [
        {"approval_hash": approval_hash(item), "public_input": public_input(item)}
        for item in candidates
    ]
