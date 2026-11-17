import json
from unittest.mock import Mock

from offscroll.cli import main
from offscroll.config import SourceSettings
from offscroll.diagnostics import doctor
from offscroll.pipeline import safe_run_error


def test_doctor_reports_missing_settings_without_exposing_environment(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.setenv("OFFSCROLL_SOURCES", "hackernews,wikipedia,youtube")
    assert main(["doctor"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False
    assert report["checks"][0]["present"] is False
    assert report["checks"][1]["reason"] == "missing_or_invalid_database_configuration"


def test_doctor_presence_is_boolean_and_exception_details_are_hidden():
    from sqlalchemy.exc import SQLAlchemyError

    engine = Mock()
    engine.connect.side_effect = SQLAlchemyError("PRIVATE DATABASE DIAGNOSTIC")
    settings = SourceSettings(youtube_api_key="synthetic-private-value")
    report = doctor(engine, settings)
    encoded = json.dumps(report)
    assert report["ok"] is False
    assert report["checks"][0]["present"] is True
    assert "PRIVATE" not in encoded and "synthetic-private-value" not in encoded


def test_unknown_stored_error_text_is_redacted():
    assert safe_run_error("remote message with credentials") == "unclassified_error"
    assert safe_run_error(
        "youtube_http_error resource=videos http_status=403 reason=keyInvalid"
    ) == ("youtube_http_error resource=videos http_status=403 reason=keyInvalid")
    assert (
        safe_run_error("youtube_http_error reason=private-key url=private") == "youtube_http_error"
    )


def test_status_prominently_fails_for_an_unhealthy_source(monkeypatch, capsys):
    monkeypatch.setattr("offscroll.cli.load_settings", Mock())
    monkeypatch.setattr("offscroll.cli.create_db_engine", Mock())
    monkeypatch.setattr(
        "offscroll.cli.source_status",
        lambda *_: [
            {
                "source": "youtube",
                "health": "failed",
                "status": "failed",
                "error_summary": "youtube_quota_exceeded",
            }
        ],
    )
    assert main(["status"]) == 1
    output = capsys.readouterr().out
    assert 'health="failed"' in output and 'error_summary="youtube_quota_exceeded"' in output
