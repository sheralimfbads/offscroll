"""Read-only verification of the schema created by `make migrate`."""

import os

import pytest
from pydantic import ValidationError
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from offscroll.config import load_settings
from offscroll.db import create_db_engine


@pytest.mark.integration
def test_initial_migration_is_applied():
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL is unset; no integration database configured")

    try:
        engine = create_db_engine(load_settings())
    except ValidationError:
        pytest.fail("Invalid integration DATABASE_URL configuration.", pytrace=False)

    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            assert {"raw", "core", "marts"} <= set(inspector.get_schema_names())
            assert inspector.has_table("ingest_runs", schema="raw")
            columns = {
                column["name"]: column
                for column in inspector.get_columns("ingest_runs", schema="raw")
            }
            assert set(columns) == {
                "id",
                "source",
                "started_at",
                "finished_at",
                "status",
                "items_fetched",
                "error_summary",
            }
            assert inspector.get_pk_constraint("ingest_runs", schema="raw")[
                "constrained_columns"
            ] == ["id"]
            assert columns["id"]["identity"]
            assert columns["started_at"]["type"].timezone is True
            assert columns["finished_at"]["type"].timezone is True
            assert columns["finished_at"]["nullable"] is True
            assert columns["error_summary"]["nullable"] is True
            assert columns["items_fetched"]["default"] is not None
            assert (
                connection.scalar(text("SELECT version_num FROM public.alembic_version")) == "0001"
            )
    except SQLAlchemyError:
        # Never surface the underlying driver's connection string or parameters.
        pytest.fail(
            "Integration database unavailable or unmigrated. Run make migrate.", pytrace=False
        )
    finally:
        engine.dispose()
