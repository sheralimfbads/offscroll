import httpx
import pytest

from offscroll.connectors._base import ConnectorError
from offscroll.connectors._http import QuotaError, request_json


def test_retry_counts_every_attempt_and_respects_retry_after(monkeypatch):
    pauses = []
    charged = []
    monkeypatch.setattr("offscroll.connectors._http.time.sleep", pauses.append)
    responses = [httpx.Response(429, headers={"Retry-After": "12"}), httpx.Response(200, json={})]
    with httpx.Client(transport=httpx.MockTransport(lambda _: responses.pop(0))) as client:
        assert request_json(client, "https://example.org", reserve=lambda: charged.append(1)) == {}
    assert len(charged) == 2
    assert pauses == [12]


@pytest.mark.parametrize("code", [400, 403, 404])
def test_permanent_errors_are_not_retried(code):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(code, text="private error detail")

    with (
        httpx.Client(transport=httpx.MockTransport(respond)) as client,
        pytest.raises(ConnectorError, match=f"HTTP {code}") as error,
    ):
        request_json(client, "https://example.org")
    assert len(requests) == 1
    assert "private" not in str(error.value)


def test_quota_exceeded_is_clear_and_not_retried():
    charged = []
    response = httpx.Response(403, json={"error": {"errors": [{"reason": "quotaExceeded"}]}})
    with (
        httpx.Client(transport=httpx.MockTransport(lambda _: response)) as client,
        pytest.raises(QuotaError, match="quotaExceeded"),
    ):
        request_json(client, "https://example.org", reserve=lambda: charged.append(1))
    assert charged == [1]


def test_long_retry_after_stops_without_early_retry():
    response = httpx.Response(429, headers={"Retry-After": "120"})
    with (
        httpx.Client(transport=httpx.MockTransport(lambda _: response)) as client,
        pytest.raises(ConnectorError, match="long retry delay"),
    ):
        request_json(client, "https://example.org")


@pytest.mark.parametrize("failure", ["timeout", "server"])
def test_transient_failures_stop_after_three_attempts(monkeypatch, failure):
    monkeypatch.setattr("offscroll.connectors._http.time.sleep", lambda _: None)
    requests = []

    def respond(request):
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("sensitive request details")
        return httpx.Response(503)

    with (
        httpx.Client(transport=httpx.MockTransport(respond)) as client,
        pytest.raises(ConnectorError, match="3 attempts"),
    ):
        request_json(client, "https://example.org")
    assert len(requests) == 3
