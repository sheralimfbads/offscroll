"""pg_dump schema plus filtered data: backups never copy YouTube API payloads."""

import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url

from offscroll.config import Settings
from offscroll.ranking import DigestError

# Dependency order matters: foreign keys are active while restoring.
TABLES = [
    ("public.alembic_version", "SELECT * FROM public.alembic_version"),
    ("core.sources", "SELECT * FROM core.sources"),
    ("raw.ingest_runs", "SELECT * FROM raw.ingest_runs WHERE source != 'youtube'"),
    (
        "raw.api_responses",
        "SELECT * FROM raw.api_responses WHERE source != 'youtube' "
        "AND fetched_at > now() - interval '83 days'",
    ),
    ("core.items", "SELECT * FROM core.items WHERE source != 'youtube'"),
    (
        "core.item_snapshots",
        "SELECT s.* FROM core.item_snapshots s JOIN core.items i ON i.id=s.item_id "
        "WHERE i.source != 'youtube'",
    ),
    ("raw.api_quota_usage", "SELECT * FROM raw.api_quota_usage"),
    ("core.digests", "SELECT * FROM core.digests"),
    ("core.item_summaries", "SELECT * FROM core.item_summaries WHERE model = 'template'"),
    ("core.digest_items", "SELECT * FROM core.digest_items"),
]


def postgres_command(
    settings: Settings, program: str, *args: str
) -> tuple[list[str], dict[str, str]]:
    url = make_url(settings.database_url.get_secret_value())
    env = {
        **os.environ,
        "PGHOST": url.host or "",
        "PGPORT": str(url.port or 5432),
        "PGUSER": url.username or "",
        "PGPASSWORD": url.password or "",
        "PGDATABASE": url.database or "",
    }
    # Env values are inherited by name; passwords never appear in argv or diagnostics.
    command = ["docker", "run", "--rm", "-i", "--network", "host"]
    for key in ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE", "PGSSLMODE"):
        if key in env:
            command.extend(["--env", key])
    return command + ["postgres:18.7-bookworm", program, *args], env


def backup_database(engine: Engine, settings: Settings, output: Path) -> Path:
    if output.exists() or output.is_symlink():
        raise DigestError("Backup path already exists; choose a new filename.")
    output.parent.mkdir(parents=True, exist_ok=True)
    command, env = postgres_command(settings, "pg_dump", "--schema-only", "--no-owner", "--no-acl")
    # Fixed executable/options; credentials only in environment; no shell.
    schema = subprocess.run(command, env=env, capture_output=True, check=False)  # noqa: S603
    if schema.returncode:
        raise DigestError("Schema backup failed; check Docker and database connectivity.")
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as file, engine.connect() as connection:
            # One repeatable-read snapshot for all data tables. Do not migrate concurrently.
            connection = connection.execution_options(isolation_level="REPEATABLE READ")
            with connection.begin():
                file.write(schema.stdout)
                file.write(b"\nBEGIN;\n")
                template_ids: set[int] = set(
                    connection.execute(
                        text("SELECT id FROM core.item_summaries WHERE model = 'template'")
                    ).scalars()
                )
                for table, query in TABLES:
                    rows = connection.execute(text(query)).mappings()
                    for row in rows:
                        values = dict(row)
                        if table == "core.digest_items":
                            if values["lane"] == "youtube":
                                values["item_id"] = None
                            if values["summary_id"] not in template_ids:
                                values["summary_id"] = None
                        statement = sql.SQL(
                            "INSERT INTO {} ({}) OVERRIDING SYSTEM VALUE VALUES ({});\n"
                        ).format(
                            sql.Identifier(*table.split(".")),
                            sql.SQL(",").join(map(sql.Identifier, values)),
                            sql.SQL(",").join(
                                sql.Literal(Jsonb(v) if isinstance(v, (dict, list)) else v)
                                for v in values.values()
                            ),
                        )
                        file.write(statement.as_string().encode())
                    if table in {
                        "raw.ingest_runs",
                        "raw.api_responses",
                        "core.items",
                        "core.digests",
                        "core.item_summaries",
                    }:
                        reset = sql.SQL(
                            "SELECT setval(pg_get_serial_sequence({}, 'id'), "
                            "coalesce(max(id), 1), max(id) IS NOT NULL) FROM {};\n"
                        ).format(sql.Literal(table), sql.Identifier(*table.split(".")))
                        file.write(reset.as_string().encode())
                file.write(b"COMMIT;\n")
    except BaseException:
        # Never leave a partially generated backup looking complete.
        output.unlink(missing_ok=True)
        raise
    return output


def restore_database(engine: Engine, settings: Settings, path: Path) -> None:
    with engine.connect() as connection:
        tables = connection.scalar(
            text("""
            SELECT count(*) FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        """)
        )
        if tables:
            raise DigestError(
                "Restore requires a completely empty database; no data was overwritten."
            )
    command, env = postgres_command(settings, "psql", "--no-psqlrc", "--set", "ON_ERROR_STOP=1")
    with path.open("rb") as source:
        # Fixed psql argv and caller-selected file handle; no shell evaluation.
        result = subprocess.run(  # noqa: S603
            command, env=env, stdin=source, capture_output=True, check=False
        )
    if result.returncode:
        raise DigestError("Restore failed; inspect the disposable target, not credential logs.")


def expire_backups(directory: Path, *, now: datetime | None = None) -> int:
    cutoff = (now or datetime.now(UTC)) - timedelta(days=7)
    count = 0
    for path in directory.glob("offscroll-*.sql"):
        if not path.is_symlink() and datetime.fromtimestamp(path.stat().st_mtime, UTC) <= cutoff:
            path.unlink()
            count += 1
    return count
