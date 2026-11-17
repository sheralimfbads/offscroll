"""M3 database behavior with synthetic source responses; no live HTTP."""

import copy
import json
import logging
import os
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text

from offscroll.config import load_settings
from offscroll.connectors import get_connector
from offscroll.connectors._base import RawResponse
from offscroll.connectors._http import QuotaError
from offscroll.db import create_db_engine
from offscroll.operations import check_data, run_all, source_status
from offscroll.pipeline import PipelineError, execute_run
from offscroll.quota import YouTubeQuota
from offscroll.retention import purge_expired

pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).parent / "fixtures"


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
            connection.execute(text("DELETE FROM core.items"))
            connection.execute(text("DELETE FROM raw.api_responses"))
            connection.execute(text("DELETE FROM raw.ingest_runs"))
            connection.execute(text("DELETE FROM core.youtube_channels"))
            yield engine, connection
        finally:
            transaction.rollback()
    engine.dispose()


@pytest.fixture
def fake_sources(monkeypatch):
    now = datetime.now(UTC)
    hn = json.loads((FIXTURES / "hn_normal.json").read_text())
    for hit in hn["hits"]:
        hit["created_at_i"] = int(now.timestamp()) - 3600
    wiki = json.loads((FIXTURES / "wiki_daily.json").read_text())
    for index, day in enumerate(wiki["items"]):
        day["timestamp"] = (now.date() - timedelta(days=35 - index)).strftime("%Y%m%d00")
    youtube = json.loads((FIXTURES / "youtube_videos.json").read_text())
    youtube["items"][0]["snippet"]["publishedAt"] = (now - timedelta(hours=1)).isoformat()
    payloads = {"hackernews": hn, "wikipedia": wiki, "youtube": youtube}
    connectors = {}
    for source, payload in payloads.items():
        connector = copy.copy(get_connector(source))
        pages = [RawResponse("/synthetic", now, 200, payload)]
        monkeypatch.setattr(connector, "fetch", lambda *args, pages=pages, **kwargs: pages)
        connectors[source] = connector
    monkeypatch.setattr(
        "offscroll.pipeline.get_connector", lambda source, engine: connectors[source]
    )
    return list(payloads)


def test_all_sources_twice_and_quality_checks(database, fake_sources):
    engine, connection = database
    first = run_all(engine, fake_sources)
    second = run_all(engine, fake_sources)
    assert all(row["status"] == "succeeded" for row in first + second)
    assert connection.scalar(text("SELECT count(*) FROM core.items")) == 4
    assert connection.scalar(text("SELECT count(*) FROM core.item_snapshots")) == 8
    assert check_data(engine, fake_sources) == []
    status = source_status(engine, fake_sources)
    assert len(status) == 3
    assert all(row["status"] == "succeeded" and row["items"] > 0 for row in status)


def test_quality_detects_empty_stale_and_failed_sources(database, fake_sources):
    engine, connection = database
    assert "youtube:missing_items_or_snapshots" in check_data(engine, fake_sources)
    run_all(engine, fake_sources)
    connection.execute(
        text("""
        UPDATE core.item_snapshots SET captured_at = clock_timestamp() - interval '37 hours'
        WHERE item_id IN (SELECT id FROM core.items WHERE source = 'wikipedia')
    """)
    )
    connection.execute(
        text("UPDATE raw.ingest_runs SET status = 'failed' WHERE source = 'youtube'")
    )
    failures = check_data(engine, fake_sources)
    assert "wikipedia:data_not_fresh" in failures
    assert "youtube:last_run_not_succeeded" in failures


def test_retention_deletes_old_observations_even_for_refreshed_items(database, fake_sources):
    engine, connection = database
    run_all(engine, fake_sources)
    first_run = connection.scalar(text("SELECT id FROM raw.ingest_runs WHERE source = 'youtube'"))
    execute_run(engine, "youtube")
    connection.execute(
        text("""
        UPDATE core.item_snapshots SET captured_at = clock_timestamp() - interval '31 days'
        WHERE run_id = :id
    """),
        {"id": first_run},
    )
    connection.execute(
        text("""
        UPDATE raw.api_responses SET fetched_at = clock_timestamp() - interval '31 days'
        WHERE run_id = :id
    """),
        {"id": first_run},
    )
    connection.execute(
        text("""
        INSERT INTO core.youtube_channels VALUES
        ('UCexpired', '@expired', 'Old', 'UUexpired', 'science', false,
         clock_timestamp() - interval '31 days')
    """)
    )
    assert "expired_youtube_data" in check_data(engine, fake_sources)
    counts = purge_expired(engine)
    assert counts == {
        "raw_responses": 1,
        "snapshots": 1,
        "items": 0,
        "channels": 1,
        "digest_links": 0,
    }
    assert connection.scalar(text("SELECT count(*) FROM core.items WHERE source = 'youtube'")) == 1
    assert check_data(engine, fake_sources) == []
    connection.execute(
        text("""
        UPDATE core.items SET first_seen_at = clock_timestamp() - interval '32 days',
                              last_seen_at = clock_timestamp() - interval '31 days'
        WHERE source = 'youtube'
    """)
    )
    assert purge_expired(engine)["items"] == 1
    assert connection.scalar(text("SELECT count(*) FROM core.items")) == 3  # HN + Wikipedia remain.


def test_youtube_quota_atomic_guard_and_rollback_durability():
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL is unset")
    engine = create_db_engine(load_settings())
    quota_date = "SELECT (clock_timestamp() AT TIME ZONE 'America/Los_Angeles')::date"
    with engine.connect() as connection:
        day = connection.scalar(text(quota_date))
        previous = connection.scalar(
            text("SELECT units FROM raw.api_quota_usage WHERE date = :day AND source = 'youtube'"),
            {"day": day},
        )
    try:
        with engine.begin() as connection:
            connection.execute(
                text("""
                INSERT INTO raw.api_quota_usage VALUES (:day, 'youtube', 7998)
                ON CONFLICT (date, source) DO UPDATE SET units = 7998
            """),
                {"day": day},
            )
        # Reservations use a second connection; rolling back data work cannot refund them.
        with engine.connect() as connection:
            transaction = connection.begin()
            guard = YouTubeQuota(engine)
            guard.reserve()
            transaction.rollback()
            assert guard.units == 1
        with pytest.raises(QuotaError, match="guard reached"):
            YouTubeQuota(engine).reserve()
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    text(
                        "SELECT units FROM raw.api_quota_usage "
                        "WHERE date = :day AND source = 'youtube'"
                    ),
                    {"day": day},
                )
                == 7999
            )
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM raw.api_quota_usage WHERE date = :day AND source = 'youtube'"),
                {"day": day},
            )
            if previous is not None:
                connection.execute(
                    text("INSERT INTO raw.api_quota_usage VALUES (:day, 'youtube', :n)"),
                    {"day": day, "n": previous},
                )
        engine.dispose()


def test_real_youtube_connector_caches_channels_and_counts_requests(
    database, monkeypatch, tmp_path
):
    engine, connection = database
    config = tmp_path / "channels.yaml"
    config.write_text("channels: [{handle: '@example', category: science}]")
    monkeypatch.setenv("YOUTUBE_API_KEY", uuid4().hex)
    monkeypatch.setenv("YOUTUBE_CHANNELS_FILE", str(config))
    monkeypatch.setattr("offscroll.connectors.youtube.time.sleep", lambda _: None)
    requests = []

    def respond(request):
        requests.append(request.url.path)
        if request.url.path.endswith("/channels"):
            return httpx.Response(
                200,
                json={
                    "kind": "youtube#channelListResponse",
                    "items": [
                        {
                            "id": "UC" + "A" * 22,
                            "snippet": {"title": "Example channel"},
                            "contentDetails": {"relatedPlaylists": {"uploads": "UU" + "A" * 22}},
                        }
                    ],
                },
            )
        if request.url.path.endswith("/playlistItems"):
            return httpx.Response(
                200,
                json={
                    "kind": "youtube#playlistItemListResponse",
                    "items": [
                        {
                            "contentDetails": {
                                "videoId": "AAAAAAAAAAA",
                                "videoPublishedAt": (
                                    datetime.now(UTC) - timedelta(hours=1)
                                ).isoformat(),
                            }
                        },
                    ],
                },
            )
        return httpx.Response(200, json=json.loads((FIXTURES / "youtube_videos.json").read_text()))

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        first = execute_run(engine, "youtube", client=client)
        second = execute_run(engine, "youtube", client=client)
    assert first.upserted == second.upserted == 1
    assert requests.count("/youtube/v3/channels") == 1
    assert len(requests) == 5
    assert connection.scalar(text("SELECT count(*) FROM core.youtube_channels WHERE active")) == 1
    assert connection.scalar(text("SELECT count(*) FROM core.items WHERE source = 'youtube'")) == 1
    assert connection.scalar(text("SELECT count(*) FROM core.item_snapshots")) == 2


def test_missing_youtube_key_records_failure_without_http(database, monkeypatch):
    engine, connection = database
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with pytest.raises(PipelineError, match="missing_youtube_api_key"):
        execute_run(engine, "youtube")
    assert (
        connection.scalar(text("SELECT error_summary FROM raw.ingest_runs"))
        == "missing_youtube_api_key"
    )
    assert connection.scalar(text("SELECT status FROM raw.ingest_runs")) == "failed"


def test_youtube_diagnostic_survives_rollback_without_exposing_response(
    database, monkeypatch, tmp_path, caplog
):
    engine, connection = database
    key = uuid4().hex
    config = tmp_path / "channels.yaml"
    config.write_text("channels: [{handle: '@example', category: science}]")
    monkeypatch.setenv("YOUTUBE_API_KEY", key)
    monkeypatch.setenv("YOUTUBE_CHANNELS_FILE", str(config))
    response = httpx.Response(404, json={"error": {"message": f"private {key}"}})
    caplog.set_level(logging.INFO, logger="offscroll.pipeline")
    with (
        httpx.Client(transport=httpx.MockTransport(lambda _: response)) as client,
        pytest.raises(PipelineError, match="youtube_http_error") as error,
    ):
        execute_run(engine, "youtube", client=client)
    expected = "youtube_http_error resource=channels channel_index=1 http_status=404"
    assert connection.scalar(text("SELECT error_summary FROM raw.ingest_runs")) == expected
    assert connection.scalar(text("SELECT status FROM raw.ingest_runs")) == "failed"
    assert connection.scalar(text("SELECT count(*) FROM raw.api_responses")) == 0
    assert f"error={expected}" in caplog.text
    assert key not in str(error.value)
    assert key not in caplog.text
    assert "private" not in caplog.text


def test_run_all_auth_failure_is_loud_safe_and_preserves_active_cache(
    database, monkeypatch, tmp_path, capsys
):
    from offscroll.cli import main

    engine, connection = database
    config = tmp_path / "channels.yaml"
    config.write_text("channels: [{handle: '@example', category: science}]")
    key = uuid4().hex
    monkeypatch.setenv("YOUTUBE_API_KEY", key)
    monkeypatch.setenv("YOUTUBE_CHANNELS_FILE", str(config))
    monkeypatch.setenv("OFFSCROLL_SOURCES", "youtube")
    connection.execute(
        text(
            "INSERT INTO core.youtube_channels VALUES ('UCexample', '@example', 'Example', "
            "'UUexample', 'science', true, clock_timestamp()-interval '2 days')"
        )
    )
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(
            403, json={"error": {"message": key, "errors": [{"reason": "keyInvalid"}]}}
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(
            "offscroll.operations.execute_run",
            lambda e, source: execute_run(e, source, client=client),
        )
        monkeypatch.setattr("offscroll.cli.create_db_engine", lambda _: engine)
        assert main(["run-all"]) == 1
    output = capsys.readouterr()
    assert "reason=keyInvalid" in output.out and "youtube_collection_failed" in output.err
    assert key not in output.out + output.err and len(calls) == 1
    status = source_status(engine, ["youtube"])[0]
    assert status["health"] == "failed" and "keyInvalid" in status["error_summary"]
    assert (
        connection.scalar(text("SELECT active FROM core.youtube_channels WHERE handle='@example'"))
        is True
    )
    assert connection.scalar(text("SELECT count(*) FROM raw.api_responses")) == 0
