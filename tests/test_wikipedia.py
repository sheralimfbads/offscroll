import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from offscroll.connectors._base import ConnectorError
from offscroll.connectors.wikipedia import connector, is_article, normalize_title, parse

FIXTURES = Path(__file__).parent / "fixtures"


def test_daily_series_produces_exact_week_and_baseline():
    result = parse(json.loads((FIXTURES / "wiki_daily.json").read_text()))
    assert result.fetched == 1
    assert result.rejected == 0
    record = result.records[0]
    assert record.external_id == "Example_topic"
    assert record.views == 1400
    assert record.metadata["baseline_daily_views"] == 100
    assert record.metadata["spike_ratio"] == 2
    assert record.metadata["window_start"] == "2026-11-08"
    assert record.metadata["window_end"] == "2026-11-14"
    assert record.published_at.isoformat() == "2026-11-15T00:00:00+00:00"


@pytest.mark.parametrize("fault", ["gap", "duplicate", "negative", "title", "bad_timestamp"])
def test_invalid_or_incomplete_daily_series_is_rejected(fault):
    payload = json.loads((FIXTURES / "wiki_daily.json").read_text())
    if fault == "gap":
        payload["items"].pop(4)
    elif fault == "duplicate":
        payload["items"][4] = payload["items"][3]
    elif fault == "negative":
        payload["items"][4]["views"] = -1
    elif fault == "title":
        payload["items"][4]["article"] = "Another_topic"
    else:
        payload["items"][4]["timestamp"] = "2026130100"
    assert parse(payload).rejected == 1
    assert parse(payload).records == []


def test_zero_baseline_is_unknown_not_infinity():
    payload = json.loads((FIXTURES / "wiki_daily.json").read_text())
    for day in payload["items"][:28]:
        day["views"] = 0
    assert parse(payload).records[0].metadata["spike_ratio"] is None


def test_top_filters_namespaces_and_counts_malformed_hits():
    result = parse(json.loads((FIXTURES / "wiki_top.json").read_text()))
    assert result.records == []
    assert result.fetched == 3
    assert result.rejected == 1
    assert not is_article("Special:Search")
    assert not is_article("Main_Page")
    assert is_article("Star_Trek:_Voyager")
    assert normalize_title(" Example topic ") == "Example_topic"


def test_fetch_is_serial_top_seven_days_then_bounded_candidates(monkeypatch):
    pauses = []
    monkeypatch.setattr("offscroll.connectors.wikipedia.time.sleep", pauses.append)
    top = json.loads((FIXTURES / "wiki_top.json").read_text())
    daily = json.loads((FIXTURES / "wiki_daily.json").read_text())
    requests = []

    def respond(request):
        requests.append(request)
        assert "offscroll/issues" in request.headers["User-Agent"]
        return httpx.Response(200, json=top if "/top/" in request.url.path else daily)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        pages = connector.fetch(client, end_date=date(2026, 11, 14))
    assert len(pages) == 9  # Seven top lists, two valid article candidates.
    assert requests[0].url.path.endswith("2026/11/08")
    assert requests[6].url.path.endswith("2026/11/14")
    assert requests[7].url.path.endswith("daily/2026101100/2026111400")
    assert len(pauses) == 8
    assert all(delay == 1 for delay in pauses)


def test_missing_daily_data_fails_clearly():
    with pytest.raises(ConnectorError, match="no pageview"):
        parse({"items": []})
