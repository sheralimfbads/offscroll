"""Read-only doctor: settings presence, database health, source/lane/export evidence."""

import json
from datetime import UTC, datetime
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from offscroll.config import SourceSettings
from offscroll.delivery import public_lanes, render_page
from offscroll.digests import digest_identity, read_digest, shared_candidates, youtube_funnel
from offscroll.operations import check_data, source_status
from offscroll.ranking import DigestError, digest_window


def doctor(
    engine: Engine | None, settings: SourceSettings, site: Path = Path("site")
) -> dict[str, object]:
    checks: list[dict[str, object]] = []

    def add(name: str, ok: bool, **details: object) -> None:
        checks.append({"check": name, "ok": ok, **details})

    def result() -> dict[str, object]:
        return {"ok": all(row["ok"] for row in checks), "checks": checks}

    sources = settings.enabled_sources
    key_present = bool(
        settings.youtube_api_key and settings.youtube_api_key.get_secret_value().strip()
    )
    add(
        "youtube_key",
        "youtube" not in sources or key_present,
        present=key_present,
        enabled="youtube" in sources,
    )
    if engine is None:
        add("database", False, reason="missing_or_invalid_database_configuration")
        return result()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            add("database", True)
            expected = set(ScriptDirectory("migrations").get_heads())
            actual = set(MigrationContext.configure(connection).get_current_heads())
            add("migrations", actual == expected, expected=sorted(expected), actual=sorted(actual))
            if actual != expected:
                return result()
        failures = check_data(engine, sources)
        add("data_quality", not failures, problems=failures)
        for row in source_status(engine, sources):
            add("source:" + str(row["source"]), row["health"] == "ok", **row)
        with engine.connect() as connection:
            now = connection.scalar(text("SELECT clock_timestamp()")) or datetime.now(UTC)
            window = digest_window(now)
            candidates = shared_candidates(connection, window, now)
            for source in ("hackernews", "wikipedia"):
                count = sum(item.source == source for item in candidates)
                add(
                    "lane:" + source,
                    source not in sources or count > 0,
                    candidates=count,
                    enabled=source in sources,
                )
            funnel = youtube_funnel(connection, window, now)
            add(
                "lane:youtube",
                "youtube" not in sources or funnel["selected"] > 0,
                funnel=funnel,
                enabled="youtube" in sources,
            )
            units = int(
                connection.scalar(
                    text(
                        "SELECT coalesce(sum(units), 0) FROM raw.api_quota_usage "
                        "WHERE source='youtube' AND "
                        "date=(clock_timestamp() AT TIME ZONE 'America/Los_Angeles')::date"
                    )
                )
                or 0
            )
            add(
                "youtube_quota", "youtube" not in sources or units < 7999, units=units, ceiling=7999
            )
        try:
            identity = digest_identity(engine)
            lanes = public_lanes(read_digest(engine, purge=False))
            counts = {source: len(items) for source, items in lanes.items()}
            add(
                "digest",
                all(counts[source] > 0 for source in sources),
                lane_counts=counts,
                digest=identity,
            )
            path = site / "digest.json"
            if path.is_symlink() or site.is_symlink():
                raise OSError("Export symlinks are not inspected")
            artifact = json.loads(path.read_text())
            matches = (
                isinstance(artifact, dict)
                and artifact.get("digest") == identity
                and artifact.get("lanes") == lanes
            )
            matches = matches and digest_identity(engine) == identity
            html = site / "index.html"
            if matches and not html.is_symlink():
                date = datetime.fromisoformat(artifact["exported_at"]).strftime("%d %B %Y")
                matches = html.read_text() == render_page(lanes, date=date)
            else:
                matches = False
            add(
                "export",
                matches,
                reason="matches_saved_digest"
                if matches
                else "missing_provenance_or_different_digest",
            )
        except DigestError, OSError, ValueError, UnicodeError, KeyError, TypeError:
            add("export", False, reason="missing_or_invalid_digest_or_site")
    except SQLAlchemyError:
        add("database", False, reason="database_unavailable_or_schema_invalid")
    except CommandError, OSError:
        add("migrations", False, reason="migration_files_unavailable_run_from_repository_root")
    return result()
