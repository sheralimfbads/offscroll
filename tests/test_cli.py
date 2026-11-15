import runpy
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from offscroll.cli import main
from offscroll.connectors import get_connector
from offscroll.connectors._base import ConnectorError


def test_help_needs_no_database(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "purge-raw" in capsys.readouterr().out


def test_module_entry_point_needs_no_database_for_help(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(sys, "argv", ["offscroll.cli", "--help"])
    script = Path(__file__).resolve().parents[1] / "src" / "offscroll" / "cli.py"
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(script), run_name="__main__")
    assert exc.value.code == 0
    assert "purge-raw" in capsys.readouterr().out


def test_missing_database_is_safe(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert main(["digest"]) == 1
    assert "error=invalid_configuration" in capsys.readouterr().err


@pytest.mark.parametrize(
    "args", [["run", "hackernews", "--page-cap", "0"], ["transform", "--run-id", "-1"]]
)
def test_bad_arguments(args):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2


@pytest.mark.parametrize("source", ["../hackernews", "_base", "absent_source"])
def test_unknown_sources_fail_safely(source):
    with pytest.raises(ConnectorError, match="Unknown source"):
        get_connector(source)


def test_digest_prints_all_fields_and_escapes_newlines(monkeypatch, capsys):
    monkeypatch.setattr("offscroll.cli.load_settings", Mock())
    engine = Mock()
    monkeypatch.setattr("offscroll.cli.create_db_engine", Mock(return_value=engine))
    monkeypatch.setattr(
        "offscroll.cli.digest",
        lambda _: [
            {
                "score": 42,
                "comments": 3,
                "title": "A\nB",
                "url": "https://example.com/",
                "discussion_url": "https://news.ycombinator.com/item?id=123",
                "domain": "example.com",
            }
        ],
    )
    assert main(["digest"]) == 0
    output = capsys.readouterr().out
    assert len(output.splitlines()) == 1
    for key in (
        "rank=1",
        "score=42",
        "comments=3",
        'title="A\\nB"',
        "url=",
        "discussion_url=",
        "domain=",
    ):
        assert key in output
    engine.dispose.assert_called_once()
