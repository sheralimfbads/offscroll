import json
from pathlib import Path

import httpx
import pytest

from offscroll.connectors._base import ConnectorError
from offscroll.connectors.hackernews import USER_AGENT, connector, parse

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_normal_hits():
    payload = json.loads((FIXTURES / "hn_normal.json").read_text())
    parsed = parse(payload)
    assert parsed.fetched == 3
    assert parsed.rejected == 0
    assert [item.external_id for item in parsed.records] == ["1111", "2222"]
    assert parsed.records[0].domain == "example.com"
    assert parsed.records[0].discussion_url == "https://news.ycombinator.com/item?id=1111"
    assert parsed.records[0].published_at.utcoffset().total_seconds() == 0
    assert parsed.records[1].url is None
    assert parsed.records[1].domain is None
    assert len(parse(payload, min_points=0).records) == 3


def test_parse_rejects_bad_hits_without_guessing():
    parsed = parse(json.loads((FIXTURES / "hn_malformed.json").read_text()))
    assert parsed.fetched == 6
    assert parsed.rejected == 5
    assert len(parsed.records) == 1


@pytest.mark.parametrize(
    "url", ["https://user:private@example.com/", "https://example.com/?api_key=private"]
)
def test_credential_bearing_urls_are_rejected(url):
    payload = json.loads((FIXTURES / "hn_normal.json").read_text())
    payload["hits"] = [{**payload["hits"][0], "url": url}]
    result = parse(payload)
    assert result.rejected == 1
    assert result.records == []


@pytest.fixture
def delays(monkeypatch):
    waits = []
    monkeypatch.setattr("offscroll.connectors.hackernews.time.sleep", waits.append)
    monkeypatch.setattr("offscroll.connectors.hackernews.secrets.randbelow", lambda _: 0)
    return waits


def empty_page():
    return {"hits": [], "nbHits": 0, "nbPages": 0}


def test_request_params_agent_and_pagination(delays):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.params["tags"] == "story"
        assert request.url.params["hitsPerPage"] == "1000"
        assert "points>=40" in request.url.params["numericFilters"]
        assert request.headers["User-Agent"] == USER_AGENT
        assert "https://github.com/sheralimfbads/offscroll/issues" in USER_AGENT
        return httpx.Response(200, json={"hits": [{}], "nbHits": 2, "nbPages": 2})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        pages = connector.fetch(client, min_points=40)
    assert len(pages) == 2
    assert [r.url.params["page"] for r in requests] == ["0", "1"]
    assert delays == [0.5]
    assert all(p.endpoint.startswith("/api/v1/search_by_date?") for p in pages)


@pytest.mark.parametrize("failure", [429, 500, 503, "timeout"])
def test_retries_transient_failures_then_succeeds(delays, failure):
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            if failure == "timeout":
                raise httpx.ReadTimeout("private request context", request=request)
            return httpx.Response(failure)
        return httpx.Response(200, json=empty_page())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert len(connector.fetch(client)) == 1
    assert attempts == 3
    assert delays == [1, 2]


def test_retry_exhaustion_is_bounded_and_safe(delays, caplog):
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, text="private response body")

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ConnectorError, match="3 attempts"),
    ):
        connector.fetch(client)
    assert attempts == 3
    assert delays == [1, 2]
    assert "private response" not in caplog.text


@pytest.mark.parametrize("failure", [400, 403, "connection", "json", "envelope"])
def test_permanent_failure_is_not_retried(delays, failure):
    def handler(request):
        if failure == "connection":
            raise httpx.ConnectError("private context", request=request)
        if failure == "json":
            return httpx.Response(200, text="not JSON")
        if failure == "envelope":
            return httpx.Response(200, json={"hits": []})
        return httpx.Response(failure)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ConnectorError),
    ):
        connector.fetch(client)
    assert delays == []


def test_page_cap_warns_about_truncation(delays, caplog):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"hits": [{}], "nbHits": 9, "nbPages": 9})
        )
    ) as client:
        assert len(connector.fetch(client, page_cap=2)) == 2
    assert "event=truncated" in caplog.text
    assert "nb_hits=9 fetched=2" in caplog.text


def test_bad_envelope_parse_fails():
    with pytest.raises(ConnectorError, match="hits list"):
        parse({"hits": None})


def test_hn_respects_retry_after_and_disables_redirects(monkeypatch):
    from offscroll.connectors.hackernews import _request

    pauses = []
    monkeypatch.setattr("offscroll.connectors.hackernews.time.sleep", pauses.append)
    replies = [httpx.Response(429, headers={"Retry-After": "20"}), httpx.Response(200, json={})]
    with httpx.Client(transport=httpx.MockTransport(lambda _: replies.pop(0))) as client:
        _request(client, {})
    assert pauses == [20]
    requests = []
    with (
        httpx.Client(
            follow_redirects=True,
            transport=httpx.MockTransport(
                lambda request: (
                    requests.append(request)
                    or httpx.Response(302, headers={"Location": "https://elsewhere.example/"})
                )
            ),
        ) as client,
        pytest.raises(ConnectorError, match="HTTP 302"),
    ):
        _request(client, {})
    assert len(requests) == 1
