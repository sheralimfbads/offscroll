from datetime import UTC, datetime
from unittest.mock import Mock

import httpx
import pytest

from offscroll.cloud import CloudBudgetError, cloud_budget, validate_cloud_runs
from offscroll.connectors._http import QuotaError
from offscroll.quota import YouTubeQuota

NOW = datetime(2026, 11, 17, 12, tzinfo=UTC)


def history(count=1):
    return {
        "total_count": count,
        "workflow_runs": [
            {"id": i, "run_attempt": 1, "created_at": "2026-11-17T11:59:00Z"}
            for i in range(1, count + 1)
        ],
    }


def test_daily_reservation_counts_failed_and_queued_builds_conservatively():
    assert validate_cloud_runs(history(30), 1, NOW) == 6000
    with pytest.raises(CloudBudgetError):
        validate_cloud_runs(history(31), 1, NOW)


@pytest.mark.parametrize(
    "fault", ["missing", "truncated", "duplicate", "retry", "old", "future", "naive"]
)
def test_uncertain_history_fails_closed(fault):
    data = history(2)
    if fault == "missing":
        data["workflow_runs"][0]["id"] = 3
    elif fault == "truncated":
        data["total_count"] = 3
    elif fault == "duplicate":
        data["workflow_runs"][1]["id"] = 1
    elif fault == "retry":
        data["workflow_runs"][0]["run_attempt"] = 2
    else:
        data["workflow_runs"][0]["created_at"] = {
            "old": "2026-11-17T11:00:00Z",
            "future": "2026-11-17T13:00:00Z",
            "naive": "2026-11-17T11:59:00",
        }[fault]
    with pytest.raises(CloudBudgetError):
        validate_cloud_runs(data, 1, NOW)


def test_budget_request_covers_midnight_overlap_and_hides_provider_errors(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "sheralimfbads/offscroll")
    monkeypatch.setenv("GH_TOKEN", "synthetic-test-token")
    monkeypatch.setenv("GITHUB_RUN_ID", "1")
    monkeypatch.setenv("YOUTUBE_RUN_LIMIT", "200")

    def respond(request):
        assert request.url.params["created"] == ">=2026-11-17T07:00:00+00:00"
        assert request.headers["Authorization"] == "Bearer synthetic-test-token"
        return httpx.Response(200, json=history())

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert cloud_budget(client, now=NOW) == 200
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(403, text="PRIVATE"))
        ) as client,
        pytest.raises(CloudBudgetError) as exc,
    ):
        cloud_budget(client, now=NOW)
    assert "PRIVATE" not in str(exc.value)


def test_per_run_cap_stops_before_database_or_network():
    engine = Mock()
    quota = YouTubeQuota(engine, units=200, limit=200)
    with pytest.raises(QuotaError, match="per-run"):
        quota.reserve()
    engine.begin.assert_not_called()
