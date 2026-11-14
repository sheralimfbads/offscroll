import runpy
import traceback
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from alembic import context
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from offscroll.config import load_settings
from offscroll.db import create_db_engine, create_session_factory


@pytest.fixture(autouse=True)
def block_connections(monkeypatch):
    blocked = Mock(side_effect=AssertionError("Unit tests must not connect to PostgreSQL"))
    monkeypatch.setattr("psycopg.connect", blocked)
    return blocked


@pytest.fixture
def settings(monkeypatch):
    password = uuid4().hex
    monkeypatch.setenv(
        "DATABASE_URL", f"postgresql+psycopg://test_user:{password}@127.0.0.1/test_database"
    )
    return load_settings()


def test_engine_factory_uses_safe_options(settings, monkeypatch):
    engine = Mock(spec=Engine)
    create_engine = Mock(return_value=engine)
    monkeypatch.setattr("offscroll.db.create_engine", create_engine)

    assert create_db_engine(settings) is engine

    create_engine.assert_called_once_with(
        settings.database_url.get_secret_value(),
        echo=False,
        echo_pool=False,
        hide_parameters=True,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )


def test_engine_and_sessions_are_lazy_and_mask_passwords(settings, block_connections):
    engine = create_db_engine(settings)
    try:
        factory = create_session_factory(engine)
        with factory() as session:
            assert session.bind is engine
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.hide_parameters is True
        password = engine.url.password
        assert password
        for output in (str(engine), repr(engine), str(engine.url), repr(engine.url)):
            assert password not in output
        block_connections.assert_not_called()
    finally:
        engine.dispose()


def test_migration_connection_failure_hides_driver_message(settings, monkeypatch):
    url = settings.database_url.get_secret_value()
    monkeypatch.setattr(context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(
        "offscroll.db.create_db_engine", Mock(side_effect=SQLAlchemyError(f"Failed: {url}"))
    )
    script = Path(__file__).resolve().parents[1] / "migrations" / "env.py"
    with pytest.raises(SystemExit, match="Database migration failed") as exc:
        runpy.run_path(str(script))
    assert url not in "".join(traceback.format_exception(exc.value))


def test_migration_rejects_missing_configuration_without_connecting(monkeypatch, block_connections):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False)
    script = Path(__file__).resolve().parents[1] / "migrations" / "env.py"
    with pytest.raises(SystemExit, match="Invalid database configuration"):
        runpy.run_path(str(script))
    block_connections.assert_not_called()
