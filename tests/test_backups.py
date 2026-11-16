import os
import runpy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from offscroll.backups import expire_backups, postgres_command, restore_database
from offscroll.config import Settings
from offscroll.ranking import DigestError


def test_postgres_credentials_are_only_in_child_environment():
    settings = Settings(database_url=SecretStr("postgresql+psycopg://user:password@localhost/db"))
    command, env = postgres_command(settings, "pg_dump", "--schema-only")
    assert "password" not in " ".join(command)
    assert env["PGPASSWORD"] == "password"
    assert "postgres:18.7-bookworm" in command


def test_restore_refuses_nonempty_database_before_subprocess(tmp_path):
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.scalar.return_value = 1
    with pytest.raises(DigestError, match="empty database"):
        restore_database(engine, MagicMock(), tmp_path / "missing")


def test_backup_expiry_is_scoped_and_does_not_follow_symlinks(tmp_path):
    now = datetime.now(UTC)
    old = tmp_path / "offscroll-old.sql"
    old.write_text("old")
    stamp = (now - timedelta(days=8)).timestamp()
    os.utime(old, (stamp, stamp))
    other = tmp_path / "unrelated.sql"
    other.write_text("keep")
    link = tmp_path / "offscroll-link.sql"
    link.symlink_to(other)
    assert expire_backups(tmp_path, now=now) == 1
    assert other.exists() and link.is_symlink()


def test_secret_scanner_detects_patterns_without_reporting_values():
    scanner = runpy.run_path(str(Path("scripts/scan_secrets.py")))
    findings = scanner["findings"]
    assert findings(b"AIza" + b"A" * 35) == {"google-key"}
    assert findings(b"postgresql://" + b"user:nonplaceholder@localhost/db") == {"database-password"}
    assert findings(b"postgresql://user:ci_placeholder_password@localhost/db") == set()
