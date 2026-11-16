"""Source-independent orchestration and read-only database health assertions."""

from dataclasses import asdict

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from offscroll.connectors._base import ConnectorError
from offscroll.pipeline import PipelineError, execute_run, safe_run_error
from offscroll.retention import purge_expired


def run_all(engine: Engine, sources: list[str]) -> list[dict[str, object]]:
    purge_expired(engine)
    results: list[dict[str, object]] = []
    for source in sources:
        try:
            result = execute_run(engine, source)
        except (PipelineError, ConnectorError, SQLAlchemyError) as exc:
            results.append(
                {
                    "source": source,
                    "status": "failed",
                    "run_id": exc.run_id if isinstance(exc, PipelineError) else None,
                    "error": exc.code if isinstance(exc, PipelineError) else "source_run_failed",
                }
            )
        else:
            results.append(asdict(result))
    return results


def source_status(engine: Engine, sources: list[str]) -> list[dict[str, object]]:
    with engine.connect() as connection:
        rows = list(
            connection.execute(
                text("""
            SELECT s.source, r.id AS run_id, r.status, r.finished_at, r.error_summary,
                clock_timestamp() AS checked_at,
                (SELECT max(finished_at) FROM raw.ingest_runs
                 WHERE source=s.source AND status='succeeded') AS last_success_at,
                (SELECT max(snap.captured_at) FROM core.item_snapshots snap
                 JOIN core.items i ON i.id = snap.item_id WHERE i.source = s.source) AS data_at,
                (SELECT count(*) FROM core.items i WHERE i.source = s.source) AS items,
                (SELECT count(*) FROM core.item_snapshots snap JOIN core.items i
                 ON i.id = snap.item_id WHERE i.source = s.source) AS snapshots,
                (SELECT count(*) FROM raw.api_responses a
                 WHERE a.source = s.source) AS raw_responses,
                coalesce(q.units, 0) AS quota_units,
                (clock_timestamp() AT TIME ZONE 'America/Los_Angeles')::date AS quota_date
            FROM core.sources s
            LEFT JOIN LATERAL (
                SELECT id, status, finished_at, error_summary FROM raw.ingest_runs
                WHERE source = s.source ORDER BY started_at DESC, id DESC LIMIT 1
            ) r ON true
            LEFT JOIN raw.api_quota_usage q ON q.source = s.source
                AND q.date = (clock_timestamp() AT TIME ZONE 'America/Los_Angeles')::date
            WHERE s.source = ANY(:sources) ORDER BY s.source
        """),
                {"sources": sources},
            ).mappings()
        )

    result = []
    for row in rows:
        entry = dict(row)
        entry["error_summary"] = safe_run_error(entry["error_summary"])
        age = (
            (row["checked_at"] - row["data_at"]).total_seconds() / 3600 if row["data_at"] else None
        )
        entry["freshness_hours"] = age
        success_age = (
            (row["checked_at"] - row["last_success_at"]).total_seconds() / 3600
            if row["last_success_at"]
            else None
        )
        entry["last_success_age_hours"] = success_age
        entry["health"] = (
            "ok"
            if row["status"] == "succeeded"
            and age is not None
            and 0 <= age < 36
            and success_age is not None
            and 0 <= success_age < 36
            else "failed"
        )
        result.append(entry)
    return result


def check_data(engine: Engine, sources: list[str]) -> list[str]:
    failures = []
    with engine.connect() as connection:
        now = connection.scalar(text("SELECT clock_timestamp()"))
        for row in source_status(engine, sources):
            source = row["source"]
            if row["status"] != "succeeded":
                failures.append(f"{source}:last_run_not_succeeded")
            items, snapshots = row["items"], row["snapshots"]
            if (
                not isinstance(items, int)
                or not isinstance(snapshots, int)
                or not items
                or snapshots < items
            ):
                failures.append(f"{source}:missing_items_or_snapshots")
            if (
                row["data_at"] is None
                or not 0 <= (now - row["data_at"]).total_seconds() < 36 * 3600
            ):
                failures.append(f"{source}:data_not_fresh")
        known: set[str] = set(
            connection.execute(
                text("SELECT source FROM core.sources WHERE source = ANY(:sources)"),
                {"sources": sources},
            ).scalars()
        )
        failures.extend(f"{source}:source_missing" for source in sources if source not in known)
        checks = {
            "null_or_blank_required_item_fields": """
                SELECT count(*) FROM core.items WHERE source = ANY(:sources) AND (
                    external_id IS NULL OR trim(external_id) = '' OR kind IS NULL
                    OR title IS NULL OR trim(title) = '' OR published_at IS NULL
                    OR first_seen_at IS NULL OR last_seen_at IS NULL OR metadata IS NULL)
            """,
            "duplicate_item_keys": """
                SELECT count(*) FROM (SELECT source, external_id FROM core.items
                    WHERE source = ANY(:sources) GROUP BY source, external_id
                    HAVING count(*) > 1) duplicates
            """,
            "invalid_snapshots": """
                SELECT count(*) FROM core.item_snapshots snap
                JOIN core.items i ON i.id = snap.item_id
                JOIN raw.ingest_runs r ON r.id = snap.run_id
                WHERE i.source = ANY(:sources) AND (r.source != i.source OR snap.captured_at IS NULL
                    OR snap.captured_at > clock_timestamp()
                    OR score < 0 OR comments < 0 OR views < 0 OR likes < 0
                    OR (i.source = 'hackernews' AND score IS NULL)
                    OR (i.source = 'wikipedia' AND views IS NULL))
            """,
            "expired_youtube_data": """
                SELECT count(*) FROM (
                    SELECT 1 FROM raw.api_responses WHERE source = 'youtube'
                        AND fetched_at <= now() - interval '30 days'
                    UNION ALL SELECT 1 FROM core.items WHERE source = 'youtube'
                        AND last_seen_at <= now() - interval '30 days'
                    UNION ALL SELECT 1 FROM core.item_snapshots s
                        JOIN core.items i ON i.id = s.item_id
                        WHERE i.source = 'youtube' AND captured_at <= now() - interval '30 days'
                    UNION ALL SELECT 1 FROM core.youtube_channels
                        WHERE refreshed_at <= now() - interval '30 days'
                ) expired
            """,
        }
        for name, query in checks.items():
            if connection.scalar(text(query), {"sources": sources}):
                failures.append(name)
    return failures
