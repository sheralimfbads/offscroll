"""Explicit SQL for raw landing, replayable transforms, digests, and retention."""

import logging
import time
from contextlib import nullcontext
from dataclasses import asdict, dataclass
from typing import Literal

import httpx
from sqlalchemy import Connection, Engine, RowMapping, bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import SQLAlchemyError

from offscroll.connectors import get_connector
from offscroll.connectors._base import Connector, ConnectorError, RawResponse
from offscroll.connectors._http import GOOGLE_REASONS, QuotaError
from offscroll.connectors.youtube import MissingKeyError, YouTubeSourceError
from offscroll.retention import purge_expired

logger = logging.getLogger(__name__)


def safe_run_error(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return "unclassified_error"
    parts = value.split()
    codes = {
        "source_run_failed",
        "source_error",
        "database_error",
        "transform_error",
        "missing_youtube_api_key",
        "youtube_quota_exceeded",
        "youtube_http_error",
        "youtube_request_failed",
        "youtube_invalid_response",
        "youtube_handle_unresolved",
        "youtube_invalid_channel_metadata",
        "youtube_invalid_upload_metadata",
    }
    if not parts or parts[0] not in codes:
        return "unclassified_error"
    safe = [parts[0]]
    for part in parts[1:]:
        key, _, detail = part.partition("=")
        if (
            (key == "resource" and detail in {"channels", "playlistItems", "videos"})
            or (key == "reason" and detail in GOOGLE_REASONS)
            or (
                key in {"channel_index", "http_status"}
                and detail.isascii()
                and detail.isdecimal()
                and len(detail) <= 3
            )
        ):
            safe.append(part)
    return " ".join(safe)


class PipelineError(Exception):
    """A safe message that can be shown without exposing underlying exceptions."""

    def __init__(
        self, message: str, *, run_id: int | None = None, code: str = "source_run_failed"
    ) -> None:
        super().__init__(message)
        self.run_id = run_id
        self.code = safe_run_error(code) or "source_run_failed"


@dataclass
class RunSummary:
    run_id: int
    source: str
    status: str = "running"
    fetched: int = 0
    upserted: int = 0
    rejected: int = 0


INSERT_RAW = text("""
    INSERT INTO raw.api_responses (run_id, source, endpoint, fetched_at, http_status, payload)
    VALUES (:run_id, :source, :endpoint, :fetched_at, :http_status, :payload)
""").bindparams(bindparam("payload", type_=JSONB))

UPSERT_ITEM = text("""
    INSERT INTO core.items
        (source, external_id, kind, title, url, discussion_url, domain, author,
         published_at, first_seen_at, last_seen_at, metadata)
    VALUES (:source, :external_id, :kind, :title, :url, :discussion_url, :domain,
            :author, :published_at, :captured_at, :captured_at, :metadata)
    ON CONFLICT (source, external_id) DO UPDATE SET
        kind = EXCLUDED.kind, title = EXCLUDED.title, url = EXCLUDED.url,
        discussion_url = EXCLUDED.discussion_url, domain = EXCLUDED.domain,
        author = EXCLUDED.author, published_at = EXCLUDED.published_at,
        metadata = EXCLUDED.metadata, last_seen_at = EXCLUDED.last_seen_at
    WHERE EXCLUDED.last_seen_at >= core.items.last_seen_at
    RETURNING id
""").bindparams(bindparam("metadata", type_=JSONB))

INSERT_SNAPSHOT = text("""
    INSERT INTO core.item_snapshots (item_id, run_id, captured_at, score, comments, views, likes)
    VALUES (:item_id, :run_id, :captured_at, :score, :comments, :views, :likes)
    ON CONFLICT (item_id, run_id) DO NOTHING
""")


def _transform(
    connection: Connection,
    connector: Connector,
    pages: list[RawResponse],
    summary: RunSummary,
    min_points: int,
) -> None:
    connection.execute(
        text("""
        INSERT INTO core.sources (source, display_name, raw_retention_days, notes)
        VALUES (:source, :display_name, :days, :notes) ON CONFLICT (source) DO NOTHING
    """),
        {
            "source": connector.source,
            "display_name": connector.display_name,
            "days": connector.raw_retention_days,
            "notes": connector.notes,
        },
    )
    item_ids: set[int] = set()
    summary.fetched = 0
    for page in pages:
        parsed = connector.parse(page.payload, min_points=min_points)
        summary.fetched += parsed.fetched
        summary.rejected += parsed.rejected
        for record in parsed.records:
            params = {
                **asdict(record),
                "source": connector.source,
                "captured_at": page.fetched_at,
                "run_id": summary.run_id,
            }
            item_id: int | None = connection.execute(UPSERT_ITEM, params).scalar_one_or_none()
            if item_id is None:
                # Replaying older raw data must not overwrite newer item metadata.
                item_id = connection.execute(
                    text("""
                    SELECT id FROM core.items WHERE source = :source AND external_id = :external_id
                """),
                    params,
                ).scalar_one()
            connection.execute(INSERT_SNAPSHOT, {**params, "item_id": item_id})
            item_ids.add(int(item_id))
    summary.upserted = len(item_ids)


def execute_run(
    engine: Engine,
    source: str = "hackernews",
    *,
    mode: Literal["ingest", "transform", "run"] = "run",
    run_id: int | None = None,
    min_points: int = 20,
    page_cap: int = 5,
    client: httpx.Client | None = None,
) -> RunSummary:
    """One transaction; a savepoint protects data while preserving failed-run logs."""
    started = time.monotonic()
    failure: str | None = None
    # Run retention independently so a failed source cannot roll back the purge.
    # HN remains unchanged; YouTube raw replay can never resurrect expired payloads.
    if source == "youtube" or mode == "transform":
        purge_expired(engine)
    with engine.begin() as connection:
        if mode == "transform":
            if run_id is None:
                run_id = connection.execute(
                    text("""
                    SELECT max(r.id) FROM raw.ingest_runs r
                    WHERE EXISTS (SELECT 1 FROM raw.api_responses a WHERE a.run_id = r.id)
                """)
                ).scalar_one()
            row = (
                connection.execute(
                    text("""
                SELECT id, source FROM raw.ingest_runs WHERE id = :id FOR UPDATE
            """),
                    {"id": run_id},
                )
                .mappings()
                .first()
            )
            if row is None:
                raise PipelineError("No stored run found. Ingest a source first.")
            source = row["source"]
        connector = get_connector(source, engine)
        if mode != "transform":
            run_id = int(
                connection.execute(
                    text("""
                INSERT INTO raw.ingest_runs (source, status)
                VALUES (:source, 'running') RETURNING id
            """),
                    {"source": source},
                ).scalar_one()
            )
        if run_id is None:
            raise PipelineError("No run selected.")
        summary = RunSummary(run_id=run_id, source=source)
        connection.execute(
            text("""
            UPDATE raw.ingest_runs SET status = 'running', finished_at = NULL, error_summary = NULL
            WHERE id = :id
        """),
            {"id": run_id},
        )
        try:
            with connection.begin_nested():
                if mode == "transform":
                    rows = connection.execute(
                        text("""
                        SELECT endpoint, fetched_at, http_status, payload FROM raw.api_responses
                        WHERE run_id = :id ORDER BY fetched_at, id
                    """),
                        {"id": run_id},
                    ).mappings()
                    pages = [RawResponse(**dict(row)) for row in rows]
                    if not pages:
                        raise PipelineError("Raw responses are unavailable for this run.")
                else:
                    with nullcontext(client) if client is not None else httpx.Client() as http:
                        pages = connector.fetch(http, min_points=min_points, page_cap=page_cap)
                    summary.fetched = sum(page.items_fetched for page in pages)
                    for page in pages:
                        connection.execute(
                            INSERT_RAW,
                            {
                                "run_id": run_id,
                                "source": source,
                                "endpoint": page.endpoint,
                                "fetched_at": page.fetched_at,
                                "http_status": page.http_status,
                                "payload": page.payload,
                            },
                        )
                if mode != "ingest":
                    _transform(connection, connector, pages, summary, min_points)
        except Exception as exc:
            # Never format an exception that may contain a URL, payload, or credentials.
            if isinstance(exc, QuotaError):
                failure = "youtube_quota_exceeded"
            elif isinstance(exc, MissingKeyError):
                failure = "missing_youtube_api_key"
            elif isinstance(exc, YouTubeSourceError):
                failure = exc.safe_summary
            elif isinstance(exc, ConnectorError):
                failure = "source_error"
            elif isinstance(exc, SQLAlchemyError):
                failure = "database_error"
            else:
                failure = "transform_error"
            summary.upserted = 0  # The savepoint rolled back all data writes.
        summary.status = "failed" if failure else "succeeded"
        connection.execute(
            text("""
            UPDATE raw.ingest_runs SET finished_at = clock_timestamp(), status = :status,
                items_fetched = :fetched, items_rejected = :rejected, error_summary = :error
            WHERE id = :run_id
        """),
            {**asdict(summary), "error": failure},
        )
    logger.info(
        "event=run_summary run_id=%s source=%s status=%s "
        "fetched=%s upserted=%s rejected=%s duration=%.3f error=%s",
        summary.run_id,
        summary.source,
        summary.status,
        summary.fetched,
        summary.upserted,
        summary.rejected,
        time.monotonic() - started,
        failure or "none",
    )
    if failure:
        raise PipelineError(
            f"Run {run_id} failed ({failure}); see its safe error_summary.",
            run_id=run_id,
            code=failure,
        )
    return summary


def digest(engine: Engine) -> list[RowMapping]:
    with engine.connect() as connection:
        return list(
            connection.execute(
                text("""
            SELECT score, comments, title, url, discussion_url, domain
            FROM marts.latest_item_metrics
            WHERE source = 'hackernews' AND published_at > now() - interval '7 days'
                  AND published_at <= now()
            ORDER BY score DESC NULLS LAST, published_at DESC, external_id
            LIMIT 15
        """)
            ).mappings()
        )


def purge_raw(engine: Engine) -> int:
    """Compatibility wrapper: purge all expired data and return raw rows deleted."""
    return purge_expired(engine)["raw_responses"]
