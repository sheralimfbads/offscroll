"""Database tests run inside a rollback-only outer transaction; HTTP stays mocked."""

import json
import logging
import os
import time
from contextlib import contextmanager, nullcontext
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from offscroll.config import load_settings
from offscroll.connectors._base import ParseResult
from offscroll.connectors.hackernews import connector, parse
from offscroll.db import create_db_engine
from offscroll.pipeline import PipelineError, digest, execute_run, purge_raw

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
            # These deletes and every pipeline write are rolled back after each test.
            # Assertions count all sources, so isolate from pre-existing Wikipedia/YouTube rows.
            connection.execute(text("DELETE FROM core.items"))
            connection.execute(text("DELETE FROM raw.api_responses"))
            yield engine, connection
        finally:
            transaction.rollback()
    engine.dispose()


@pytest.fixture
def payload():
    data = json.loads((FIXTURES / "hn_normal.json").read_text())
    for hit in data["hits"]:
        hit["created_at_i"] = int(time.time()) - 3600
    return data


def mock_client(payload):
    return httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)))


def test_two_runs_and_replay_are_idempotent(database, payload):
    engine, connection = database
    with mock_client(payload) as client:
        first = execute_run(engine, client=client)
        for hit in payload["hits"][:2]:
            hit["title"] = "Updated title"
            hit["points"] += 100
        second = execute_run(engine, client=client)
    assert first.upserted == second.upserted == 2
    assert connection.scalar(text("SELECT count(*) FROM core.items")) == 2
    assert connection.scalar(text("SELECT count(*) FROM core.item_snapshots")) == 4
    assert (
        connection.scalar(
            text("""
        SELECT count(*) FROM (
            SELECT source, external_id FROM core.items
            GROUP BY source, external_id HAVING count(*) > 1
        ) duplicates
    """)
        )
        == 0
    )
    assert list(
        connection.execute(
            text("""
        SELECT count(*) FROM core.item_snapshots GROUP BY item_id
    """)
        ).scalars()
    ) == [2, 2]
    replay = execute_run(engine, mode="transform", run_id=first.run_id)
    assert replay.run_id == first.run_id
    assert connection.scalar(text("SELECT count(*) FROM core.item_snapshots")) == 4
    assert connection.scalar(text("SELECT min(score) FROM marts.latest_item_metrics")) == 150
    assert connection.scalar(text("SELECT min(title) FROM core.items")) == "Updated title"


def test_ingest_then_transform_latest(database, payload):
    engine, connection = database
    with mock_client(payload) as client:
        ingested = execute_run(engine, mode="ingest", client=client)
    assert ingested.fetched == 3
    assert ingested.upserted == 0
    assert connection.scalar(text("SELECT count(*) FROM core.items")) == 0
    transformed = execute_run(engine, mode="transform")
    assert transformed.run_id == ingested.run_id
    assert transformed.upserted == 2
    assert connection.scalar(text("SELECT count(*) FROM raw.api_responses")) == 1


def test_rejected_hits_are_logged(database):
    engine, connection = database
    payload = json.loads((FIXTURES / "hn_malformed.json").read_text())
    with mock_client(payload) as client:
        summary = execute_run(engine, client=client)
    assert summary.rejected == 5
    assert summary.fetched == 6
    assert summary.upserted == 1
    row = (
        connection.execute(
            text("""
        SELECT status, items_fetched, items_rejected, finished_at, error_summary
        FROM raw.ingest_runs WHERE id = :id
    """),
            {"id": summary.run_id},
        )
        .mappings()
        .one()
    )
    assert row["status"] == "succeeded"
    assert row["items_fetched"] == 6
    assert row["items_rejected"] == 5
    assert row["finished_at"] is not None
    assert row["error_summary"] is None


@pytest.mark.parametrize("failure", ["parse", "database"])
def test_failure_rolls_back_data_but_keeps_safe_run_record(
    database, payload, monkeypatch, caplog, failure
):
    engine, connection = database

    def fail_parse(*args, **kwargs):
        if failure == "parse":
            raise ValueError("private payload that must never be logged")
        result = parse(payload)
        return ParseResult([replace(result.records[0], score=-1)], result.fetched, 0)

    monkeypatch.setattr(connector, "parse", fail_parse)
    caplog.set_level(logging.INFO, logger="offscroll.pipeline")
    with mock_client(payload) as client, pytest.raises(PipelineError) as exc:
        execute_run(engine, client=client)
    run_id = exc.value.run_id
    assert run_id is not None
    row = (
        connection.execute(
            text("""
        SELECT status, error_summary FROM raw.ingest_runs WHERE id = :id
    """),
            {"id": run_id},
        )
        .mappings()
        .one()
    )
    assert row["status"] == "failed"
    assert row["error_summary"] in {"transform_error", "database_error"}
    assert connection.scalar(text("SELECT count(*) FROM raw.api_responses")) == 0
    assert connection.scalar(text("SELECT count(*) FROM core.items")) == 0
    assert "private payload" not in caplog.text
    assert caplog.text.count("event=run_summary") == 1
    assert "status=failed" in caplog.text


def test_digest_orders_latest_scores_and_limits_recent_items(database, payload):
    engine, _ = database
    base = payload["hits"][0]
    hits = [{**base, "objectID": str(10000 + n), "points": 20 + n} for n in range(18)]
    hits += [
        {**base, "objectID": "20000", "points": 999, "created_at_i": int(time.time()) - 8 * 86400}
    ]
    hits += [{**base, "objectID": "20001", "points": 998, "created_at_i": int(time.time()) + 86400}]
    with mock_client({"hits": hits, "nbHits": len(hits), "nbPages": 1}) as client:
        execute_run(engine, client=client)
    rows = digest(engine)
    assert len(rows) == 15
    assert [row["score"] for row in rows] == list(range(37, 22, -1))


def test_purge_only_expired_raw_responses(database, payload):
    engine, connection = database
    with mock_client(payload) as client:
        old = execute_run(engine, client=client)
        recent = execute_run(engine, client=client)
    connection.execute(
        text("""
        UPDATE raw.api_responses SET fetched_at = now() - interval '91 days' WHERE run_id = :id
    """),
        {"id": old.run_id},
    )
    assert purge_raw(engine) == 1
    assert purge_raw(engine) == 0
    assert connection.scalar(text("SELECT run_id FROM raw.api_responses")) == recent.run_id
    assert connection.scalar(text("SELECT count(*) FROM core.items")) == 2
    assert connection.scalar(text("SELECT count(*) FROM core.item_snapshots")) == 4
