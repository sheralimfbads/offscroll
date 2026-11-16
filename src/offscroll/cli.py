"""Command-line entry point for the metadata pipeline."""

import argparse
import json
import logging
import sys
from pathlib import Path

from pydantic import ValidationError
from pydantic_settings import SettingsError
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from offscroll.backups import backup_database, expire_backups, restore_database
from offscroll.config import SourceSettings, load_settings
from offscroll.connectors._base import ConnectorError
from offscroll.db import create_db_engine
from offscroll.delivery import export_site
from offscroll.diagnostics import doctor
from offscroll.digests import build_digest, read_digest, render_digest, summary_review_inputs
from offscroll.operations import check_data, run_all, source_status
from offscroll.pipeline import PipelineError, digest, execute_run
from offscroll.ranking import DigestError
from offscroll.retention import purge_expired


def nonnegative(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return number


def positive(value: str) -> int:
    number = nonnegative(value)
    if not number:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def print_checks(engine: Engine, sources: list[str]) -> bool:
    failures = check_data(engine, sources)
    for failure in failures:
        print(f"check=failed reason={failure}")
    if not failures:
        print("check=passed")
    return not failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("ingest", "run"):
        command = commands.add_parser(name)
        command.add_argument("source", help="Source module, e.g. hackernews")
        command.add_argument("--min-points", type=nonnegative, default=20)
        command.add_argument("--page-cap", type=positive, default=5)
    transform = commands.add_parser("transform")
    transform.add_argument("--run-id", type=positive, help="Default: latest run with raw responses")
    transform.add_argument("--min-points", type=nonnegative, default=20)
    for name in ("digest", "explain-digest", "build-digest"):
        command = commands.add_parser(name)
        command.add_argument("--week", help="ISO week, e.g. 2026-W46")
        if name == "build-digest":
            command.add_argument("--config", type=Path, default=Path("config/ranking.yaml"))
    top = commands.add_parser("top")
    top.add_argument("source", choices=["hackernews"])
    commands.add_parser("purge-raw")
    commands.add_parser("run-all")
    commands.add_parser("status")
    health = commands.add_parser("doctor")
    health.add_argument("--site", type=Path, default=Path("site"))
    commands.add_parser("summary-inputs")
    backup = commands.add_parser("backup")
    backup.add_argument("--output", type=Path, required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("--input", type=Path, required=True)
    cleanup = commands.add_parser("expire-backups")
    cleanup.add_argument("--directory", type=Path, default=Path("backups"))
    export = commands.add_parser("export-site")
    export.add_argument("--output", type=Path, default=Path("site"))
    commands.add_parser("check-data")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="level=%(levelname)s %(message)s")
    # httpx INFO messages contain request URLs; source logs use only safe fields.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    engine = None
    try:
        if args.command == "expire-backups":
            print(f"expired_backups={expire_backups(args.directory)}")
            return 0
        if args.command == "doctor":
            try:
                engine = create_db_engine(load_settings())
            except ValidationError, SettingsError:
                engine = None
            report = doctor(engine, SourceSettings(), args.site)
            print(json.dumps(report, default=str, sort_keys=True))
            return 0 if report["ok"] else 1
        engine = create_db_engine(load_settings())
        if args.command in ("ingest", "run"):
            execute_run(
                engine,
                args.source,
                mode=args.command,
                min_points=args.min_points,
                page_cap=args.page_cap,
            )
        elif args.command == "transform":
            execute_run(engine, mode="transform", run_id=args.run_id, min_points=args.min_points)
        elif args.command == "purge-raw":
            print(
                " ".join(f"deleted_{name}={count}" for name, count in purge_expired(engine).items())
            )
        elif args.command == "run-all":
            sources = SourceSettings().enabled_sources
            results = run_all(engine, sources)
            columns = ("source", "status", "run_id", "fetched", "upserted", "rejected", "error")
            print("\t".join(columns))
            for result in results:
                print("\t".join(str(result.get(column, "-")) for column in columns))
                if result.get("source") == "youtube" and result.get("status") == "failed":
                    print(
                        "error=youtube_collection_failed Check the reported code: key presence, "
                        "API enablement/key restrictions, or quota. No videos were refreshed.",
                        file=sys.stderr,
                    )
            healthy = print_checks(engine, sources)
            return 0 if healthy and all(r["status"] == "succeeded" for r in results) else 1
        elif args.command == "status":
            status_rows = source_status(engine, SourceSettings().enabled_sources)
            for status_row in status_rows:
                print(" ".join(f"{k}={json.dumps(v, default=str)}" for k, v in status_row.items()))
            return 0 if status_rows and all(r["health"] == "ok" for r in status_rows) else 1
        elif args.command == "check-data":
            return 0 if print_checks(engine, SourceSettings().enabled_sources) else 1
        elif args.command == "backup":
            backup_database(engine, load_settings(), args.output)
            print("status=backed_up")
        elif args.command == "restore":
            restore_database(engine, load_settings(), args.input)
            print("status=restored")
        elif args.command == "export-site":
            export_site(engine, args.output)
            print("status=exported")
        elif args.command == "summary-inputs":
            for entry in summary_review_inputs(engine):
                print(json.dumps(entry, ensure_ascii=True))
        elif args.command == "build-digest":
            digest_id = build_digest(engine, week=args.week, config_path=args.config)
            print(f"digest_id={digest_id} status=built")
        elif args.command in ("digest", "explain-digest"):
            print(
                render_digest(
                    read_digest(engine, week=args.week, explain=args.command == "explain-digest")
                )
            )
        else:
            rows = digest(engine)
            if not rows:
                print("No Hacker News stories in the last 7 days.")
            for rank, row in enumerate(rows, 1):
                print(
                    f"rank={rank} "
                    + " ".join(
                        f"{key}={json.dumps(value, ensure_ascii=False)}"
                        for key, value in row.items()
                    )
                )
    except ValidationError, SettingsError:
        print("error=invalid_configuration Check exported environment settings.", file=sys.stderr)
        return 1
    except DigestError as exc:
        print(f"error=digest message={json.dumps(str(exc))}", file=sys.stderr)
        return 1
    except (PipelineError, ConnectorError) as exc:
        print(f"error=pipeline message={json.dumps(str(exc))}", file=sys.stderr)
        return 1
    except OSError:
        print("error=filesystem Check local paths and permissions.", file=sys.stderr)
        return 1
    except SQLAlchemyError:
        print(
            "error=database_unavailable Check database connectivity and migrations.",
            file=sys.stderr,
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
