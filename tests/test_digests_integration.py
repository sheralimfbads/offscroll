"""Persisted lanes, transactional rebuilds, SQL isolation, and archive retention."""

import os
from contextlib import contextmanager, nullcontext
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from offscroll.config import load_settings
from offscroll.connectors._base import Record
from offscroll.db import create_db_engine
from offscroll.digests import build_digest, read_digest, render_digest
from offscroll.pipeline import INSERT_SNAPSHOT, UPSERT_ITEM
from offscroll.ranking import DigestError
from offscroll.retention import purge_expired

pytestmark = pytest.mark.integration


@pytest.fixture
def database(monkeypatch):
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL is unset")
    engine = create_db_engine(load_settings())
    with engine.connect() as connection:
        transaction = connection.begin()

        @contextmanager
        def begin():
            with connection.begin_nested():
                yield connection

        monkeypatch.setattr(engine, "begin", begin)
        monkeypatch.setattr(engine, "connect", lambda: nullcontext(connection))
        try:
            connection.execute(text("DELETE FROM core.digests"))
            connection.execute(text("DELETE FROM core.item_summaries"))
            connection.execute(text("DELETE FROM core.items"))
            connection.execute(text("DELETE FROM raw.api_responses"))
            connection.execute(text("DELETE FROM raw.ingest_runs"))
            yield engine, connection
        finally:
            transaction.rollback()
    engine.dispose()


@pytest.fixture
def seeded(database):
    engine, connection = database
    now = datetime.now(UTC)
    for source in ("hackernews", "wikipedia", "youtube"):
        run_id = connection.execute(
            text(
                "INSERT INTO raw.ingest_runs (source, status) "
                "VALUES (:source, 'succeeded') RETURNING id"
            ),
            {"source": source},
        ).scalar_one()
        for i in range(8):
            is_video = source == "youtube"
            external_id = f"video{i:06d}" if is_video else f"{source}-{i}"
            record = Record(
                external_id=external_id,
                kind="video" if is_video else "topic",
                title=(
                    f"Compiler engineering {i}" if source != "wikipedia" else f"Ocean animal {i}"
                ),
                url=f"https://www.youtube.com/watch?v={external_id}"
                if is_video
                else f"https://example{i}.org/{source}",
                discussion_url=None,
                domain=f"example{i}.org" if source == "hackernews" else f"{source}.org",
                author=None,
                published_at=now - timedelta(days=2),
                score=100 - i,
                comments=10 - i,
                views=1000 - i,
                likes=30,
                metadata={"spike_ratio": float(8 - i)}
                if not is_video
                else {
                    "channel_id": f"channel{max(i, 1)}",
                    "privacy_status": "public",
                    "embeddable": True,
                    "thumbnails": {"default": "https://i.ytimg.com/vi/example/default.jpg"},
                    "category": "science",
                },
            )
            params = {
                **asdict(record),
                "source": source,
                "captured_at": now - timedelta(hours=1),
                "run_id": run_id,
            }
            item_id = connection.execute(UPSERT_ITEM, params).scalar_one()
            connection.execute(INSERT_SNAPSHOT, {**params, "item_id": item_id})
    return engine, connection, now


def test_three_lanes_rebuild_and_cached_templates(seeded):
    engine, connection, now = seeded
    first = build_digest(engine, now=now)
    second = build_digest(engine, now=now + timedelta(minutes=1))
    assert first == second
    assert connection.scalar(text("SELECT count(*) FROM core.digests")) == 1
    assert connection.scalar(text("SELECT count(*) FROM core.digest_items")) == 15
    assert connection.scalar(text("SELECT count(*) FROM core.item_summaries")) == 11
    rows = (
        connection.execute(text("SELECT * FROM core.digest_items ORDER BY lane, lane_rank"))
        .mappings()
        .all()
    )
    videos = [row for row in rows if row["lane"] == "youtube"]
    assert len(videos) == 4
    assert [row["content"]["video_id"] for row in videos] == [
        "video000000",
        "video000002",
        "video000003",
        "video000004",
    ]
    assert all(
        row["final_score"] is None
        and row["score_breakdown"] == {}
        and row["cluster"] == []
        and row["summary_id"] is None
        for row in videos
    )
    assert all(set(row["content"]) == {"video_id", "url"} for row in videos)
    lanes = read_digest(engine, now=now + timedelta(minutes=1), explain=True)
    assert [len(lanes[s]) for s in ("hackernews", "wikipedia", "youtube")] == [6, 5, 4]
    assert lanes["youtube"][0]["views"] == 1000
    assert lanes["youtube"][0]["title"] == "Compiler engineering 0"
    for entry in lanes["youtube"]:
        assert set(entry) == {
            "lane_rank",
            "video_id",
            "url",
            "title",
            "views",
            "likes",
            "comments",
            "thumbnails",
        }
    assert "science" not in render_digest(lanes)
    # Identical YouTube/HN titles must not affect shared scoring or clustering.
    shared = {s: lanes[s] for s in ("hackernews", "wikipedia")}
    connection.execute(text("DELETE FROM core.items WHERE source = 'youtube'"))
    build_digest(engine, now=now + timedelta(minutes=1))
    without_videos = read_digest(engine, now=now + timedelta(minutes=1), explain=True)
    assert shared == {s: without_videos[s] for s in shared}
    assert without_videos["youtube"] == []


def test_youtube_eligibility_and_age_ordering(seeded):
    engine, connection, now = seeded
    connection.execute(
        text("UPDATE core.items SET published_at = :at WHERE external_id = 'video000002'"),
        {"at": now - timedelta(hours=3)},
    )
    connection.execute(
        text("UPDATE core.items SET published_at = :at WHERE external_id = 'video000003'"),
        {"at": now - timedelta(days=8)},
    )
    connection.execute(
        text(
            "UPDATE core.items SET metadata = jsonb_set(metadata, '{embeddable}', 'false') "
            "WHERE external_id = 'video000004'"
        )
    )
    connection.execute(
        text(
            "UPDATE core.items SET metadata = "
            "jsonb_set(metadata, '{privacy_status}', '\"private\"') "
            "WHERE external_id = 'video000005'"
        )
    )
    connection.execute(
        text(
            "UPDATE core.item_snapshots SET views = NULL "
            "WHERE item_id IN (SELECT id FROM core.items WHERE external_id = 'video000006')"
        )
    )
    connection.execute(
        text("UPDATE core.items SET published_at = :at WHERE external_id = 'video000007'"),
        {"at": now + timedelta(days=1)},
    )
    build_digest(engine, now=now)
    lanes = read_digest(engine, now=now)
    assert [entry["video_id"] for entry in lanes["youtube"]] == ["video000002", "video000000"]
    assert len(lanes["hackernews"]) == 6 and len(lanes["wikipedia"]) == 5


def test_archives_only_keep_video_links_even_when_source_is_refreshed(seeded):
    engine, connection, now = seeded
    digest_id = build_digest(engine, now=now)
    connection.execute(
        text("UPDATE core.digests SET generated_at = now() - interval '30 days' WHERE id = :id"),
        {"id": digest_id},
    )
    assert purge_expired(engine)["digest_links"] == 4
    entries = read_digest(engine, now=now, explain=True)["youtube"]
    assert all(set(entry) == {"lane_rank", "video_id", "url"} for entry in entries)
    assert connection.scalar(text("SELECT count(*) FROM core.items WHERE source = 'youtube'")) == 8
    assert (
        connection.scalar(
            text("SELECT count(item_id) FROM core.digest_items WHERE lane = 'youtube'")
        )
        == 0
    )
    assert purge_expired(engine)["digest_links"] == 0


def test_stale_or_nonpublic_youtube_metadata_is_never_rendered(seeded):
    engine, connection, now = seeded
    build_digest(engine, now=now)
    connection.execute(
        text(
            "UPDATE core.items SET metadata = "
            "jsonb_set(metadata, '{privacy_status}', '\"unlisted\"') "
            "WHERE source = 'youtube'"
        )
    )
    assert all(
        set(entry) == {"lane_rank", "video_id", "url"}
        for entry in read_digest(engine, now=now)["youtube"]
    )
    assert all(
        set(entry) == {"lane_rank", "video_id", "url"}
        for entry in read_digest(engine, now=now + timedelta(days=30))["youtube"]
    )


@pytest.mark.parametrize(
    "assignment",
    [
        "UPDATE core.digest_items SET final_score = 1.0 WHERE lane = 'youtube'",
        "UPDATE core.digest_items SET score_breakdown = '{\"views_per_day\": 12}' "
        "WHERE lane = 'youtube'",
        'UPDATE core.digest_items SET content = content || \'{"title": "Copied title"}\' '
        "WHERE lane = 'youtube'",
        'UPDATE core.digest_items SET content = \'{"video_id": null, "url": null}\' '
        "WHERE lane = 'youtube'",
        'UPDATE core.digest_items SET cluster = \'[{"source": "hackernews"}]\' '
        "WHERE lane = 'youtube'",
        "UPDATE core.digest_items SET lane_rank = 5 WHERE lane = 'youtube'",
    ],
)
def test_database_rejects_youtube_scores_or_copied_metadata(seeded, assignment):
    engine, connection, now = seeded
    build_digest(engine, now=now)
    with pytest.raises(IntegrityError), connection.begin_nested():
        # Assignments are test-owned literals, never external text.
        connection.execute(text(assignment))


def test_failed_rebuild_preserves_previous_digest(seeded, monkeypatch):
    engine, connection, now = seeded
    digest_id = build_digest(engine, now=now)
    before = read_digest(engine, now=now, explain=True)

    def fail(*args):
        raise DigestError("Simulated summary failure.")

    monkeypatch.setattr("offscroll.digests._store_summary", fail)
    with pytest.raises(DigestError):
        build_digest(engine, now=now + timedelta(minutes=1))
    assert read_digest(engine, now=now, explain=True) == before
    assert connection.scalar(text("SELECT id FROM core.digests")) == digest_id


def test_empty_digest_is_finite_and_missing_digest_fails(database):
    engine, _ = database
    with pytest.raises(DigestError, match="No digest"):
        read_digest(engine)
    build_digest(engine)
    lanes = read_digest(engine)
    assert all(not entries for entries in lanes.values())
    assert render_digest(lanes).endswith("That's everything for this week")


def test_iso_week_and_rolling_builds_have_separate_identities(database):
    engine, connection = database
    now = datetime(2026, 11, 16, 12, tzinfo=UTC)
    rolling = build_digest(engine, now=now)
    weekly = build_digest(engine, now=now, week="2026-W46")
    assert rolling != weekly
    assert weekly == build_digest(engine, now=now + timedelta(hours=1), week="2026-W46")
    assert connection.scalar(text("SELECT count(*) FROM core.digests")) == 2
    assert all(not lane for lane in read_digest(engine, week="2026-W46", now=now).values())


def test_video_age_has_a_one_day_floor(seeded):
    engine, connection, now = seeded
    connection.execute(
        text("UPDATE core.items SET published_at = :at WHERE external_id = 'video000000'"),
        {"at": now - timedelta(hours=20)},
    )
    connection.execute(
        text("UPDATE core.items SET published_at = :at WHERE external_id = 'video000002'"),
        {"at": now - timedelta(hours=3)},
    )
    build_digest(engine, now=now)
    videos = read_digest(engine, now=now)["youtube"]
    # Both denominators are one: the older video still wins on its larger API count.
    assert [entry["video_id"] for entry in videos[:2]] == ["video000000", "video000002"]


def test_unconfirmed_status_and_expired_observations_are_ineligible(seeded):
    engine, connection, now = seeded
    connection.execute(
        text("""
        UPDATE core.items SET metadata = metadata - 'privacy_status'
        WHERE external_id IN ('video000000', 'video000001')
    """)
    )
    connection.execute(
        text("""
        UPDATE core.item_snapshots SET captured_at = :at WHERE item_id IN (
            SELECT id FROM core.items WHERE external_id = 'video000002'
        )
    """),
        {"at": now - timedelta(days=30)},
    )
    build_digest(engine, now=now)
    videos = read_digest(engine, now=now)["youtube"]
    assert [entry["video_id"] for entry in videos] == [
        "video000003",
        "video000004",
        "video000005",
        "video000006",
    ]
