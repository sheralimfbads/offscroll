from unittest.mock import Mock

import pytest

from offscroll.cli import main
from offscroll.operations import run_all
from offscroll.pipeline import PipelineError, RunSummary


def test_run_all_continues_after_a_source_failure(monkeypatch):
    attempted = []
    monkeypatch.setattr("offscroll.operations.purge_expired", lambda _: {})

    def run(engine, source):
        attempted.append(source)
        if source == "wikipedia":
            raise PipelineError("Source failed safely", run_id=2)
        return RunSummary(run_id=len(attempted), source=source, status="succeeded", upserted=1)

    monkeypatch.setattr("offscroll.operations.execute_run", run)
    results = run_all(Mock(), ["hackernews", "wikipedia", "youtube"])
    assert attempted == ["hackernews", "wikipedia", "youtube"]
    assert [row["status"] for row in results] == ["succeeded", "failed", "succeeded"]
    assert results[1]["run_id"] == 2


@pytest.mark.parametrize(
    "failed_run,failures,expected",
    [
        (False, [], 0),
        (True, [], 1),
        (False, ["youtube:data_not_fresh"], 1),
    ],
)
def test_run_all_cli_always_runs_quality_checks(
    monkeypatch, capsys, failed_run, failures, expected
):
    monkeypatch.setattr("offscroll.cli.load_settings", Mock())
    monkeypatch.setattr("offscroll.cli.create_db_engine", Mock())
    monkeypatch.setenv("OFFSCROLL_SOURCES", "hackernews,youtube")
    monkeypatch.setattr(
        "offscroll.cli.run_all",
        lambda *_: [
            {"source": "hackernews", "status": "failed" if failed_run else "succeeded"},
            {"source": "youtube", "status": "succeeded"},
        ],
    )
    check = Mock(return_value=failures)
    monkeypatch.setattr("offscroll.cli.check_data", check)
    assert main(["run-all"]) == expected
    check.assert_called_once()
    assert check.call_args.args[1] == ["hackernews", "youtube"]
    assert "source\tstatus" in capsys.readouterr().out


def test_check_data_cli_is_nonzero_for_failed_checks(monkeypatch, capsys):
    monkeypatch.setattr("offscroll.cli.load_settings", Mock())
    monkeypatch.setattr("offscroll.cli.create_db_engine", Mock())
    monkeypatch.setattr("offscroll.cli.check_data", lambda *_: ["wikipedia:data_not_fresh"])
    assert main(["check-data"]) == 1
    assert "check=failed reason=wikipedia:data_not_fresh" in capsys.readouterr().out
