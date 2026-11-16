"""Command-line entry point for the metadata pipeline."""

import argparse
import json
import logging
import sys

from pydantic import ValidationError
from pydantic_settings import SettingsError
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from offscroll.config import SourceSettings, load_settings
from offscroll.connectors._base import ConnectorError
from offscroll.db import create_db_engine
from offscroll.operations import check_data, run_all, source_status
from offscroll.pipeline import PipelineError, digest, execute_run
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
    commands.add_parser("digest")
    commands.add_parser("purge-raw")
    commands.add_parser("run-all")
    commands.add_parser("status")
    commands.add_parser("check-data")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="level=%(levelname)s %(message)s")
    # httpx INFO messages contain request URLs; source logs use only safe fields.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    engine = None
    try:
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
            columns = ("source", "status", "run_id", "fetched", "upserted", "rejected")
            print("\t".join(columns))
            for result in results:
                print("\t".join(str(result.get(column, "-")) for column in columns))
            healthy = print_checks(engine, sources)
            return 0 if healthy and all(r["status"] == "succeeded" for r in results) else 1
        elif args.command == "status":
            for row in source_status(engine, SourceSettings().enabled_sources):
                print(" ".join(f"{k}={json.dumps(v, default=str)}" for k, v in row.items()))
        elif args.command == "check-data":
            return 0 if print_checks(engine, SourceSettings().enabled_sources) else 1
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
    except (PipelineError, ConnectorError) as exc:
        print(f"error=pipeline message={json.dumps(str(exc))}", file=sys.stderr)
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
