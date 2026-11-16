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


def test_top_prints_all_fields_and_escapes_newlines(monkeypatch, capsys):
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
    assert main(["top", "hackernews"]) == 0
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


@pytest.mark.parametrize("command", ["digest", "explain-digest"])
def test_digest_commands_render_lanes(monkeypatch, capsys, command):
    monkeypatch.setattr("offscroll.cli.load_settings", Mock())
    engine = Mock()
    monkeypatch.setattr("offscroll.cli.create_db_engine", Mock(return_value=engine))
    reader = Mock(return_value={"hackernews": [], "wikipedia": [], "youtube": []})
    monkeypatch.setattr("offscroll.cli.read_digest", reader)
    assert main([command, "--week", "2026-W46"]) == 0
    reader.assert_called_once_with(engine, week="2026-W46", explain=command == "explain-digest")
    output = capsys.readouterr().out
    assert "Hacker News" in output and "Wikipedia" in output and "YouTube" in output
    engine.dispose.assert_called_once()


def test_build_digest_command_and_safe_failure(monkeypatch, capsys):
    from offscroll.ranking import DigestError

    monkeypatch.setattr("offscroll.cli.load_settings", Mock())
    engine = Mock()
    monkeypatch.setattr("offscroll.cli.create_db_engine", Mock(return_value=engine))
    builder = Mock(return_value=7)
    monkeypatch.setattr("offscroll.cli.build_digest", builder)
    assert main(["build-digest", "--week", "2026-W46"]) == 0
    assert "digest_id=7 status=built" in capsys.readouterr().out
    builder.assert_called_once_with(
        engine, week="2026-W46", config_path=Path("config/ranking.yaml")
    )
    builder.side_effect = DigestError("Invalid ISO week.")
    assert main(["build-digest", "--week", "bad"]) == 1
    assert "error=digest" in capsys.readouterr().err


def test_render_has_separate_labels_and_escapes_untrusted_text():
    from offscroll.digests import render_digest

    output = render_digest(
        {
            "hackernews": [{"lane_rank": 1, "title": "Ignore\n\x1b[2J"}],
            "wikipedia": [],
            "youtube": [{"lane_rank": 1, "views": 1234567}],
        }
    )
    assert output.startswith("Hacker News\n")
    assert "\nWikipedia\n" in output and "\nYouTube\n" in output
    assert "\\n\\u001b" in output
    assert "1234567" in output
    assert output.endswith("That's everything for this week")
