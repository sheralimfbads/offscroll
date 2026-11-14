import runpy
import sys
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest

from offscroll.youtube import API_URL, YouTubeError, fetch_most_popular

FAKE_KEY = "fake-key-for-offline-tests"


@pytest.fixture(autouse=True)
def mock_get(monkeypatch):
    # Every test replaces HTTP access, including tests of the CLI.
    mocked = Mock(return_value=httpx.Response(200, json={"items": []}))
    monkeypatch.setattr("offscroll.youtube.httpx.get", mocked)
    return mocked


@pytest.fixture
def video_item():
    return {
        "id": "sample-id",
        "snippet": {
            "title": "Example title",
            "channelTitle": "Example channel",
            "publishedAt": "2026-01-01T12:00:00Z",
            "description": "Extra metadata should not be displayed.",
        },
        "status": {"embeddable": False},
    }


def test_default_request_and_video_metadata(mock_get, video_item):
    mock_get.return_value = httpx.Response(200, json={"items": [video_item]})

    videos = fetch_most_popular(FAKE_KEY)

    mock_get.assert_called_once_with(
        API_URL,
        params={
            "key": FAKE_KEY,
            "part": "snippet,status",
            "chart": "mostPopular",
            "regionCode": "US",
            "maxResults": 10,
        },
        timeout=10.0,
    )
    assert len(videos) == 1
    assert videos[0].id == "sample-id"
    assert videos[0].title == "Example title"
    assert videos[0].channel == "Example channel"
    assert videos[0].published_at == "2026-01-01T12:00:00Z"
    assert videos[0].watch_url == "https://www.youtube.com/watch?v=sample-id"
    assert videos[0].embeddable is False


@pytest.mark.parametrize("max_results", [1, 5, 50])
def test_configurable_parameters_and_empty_results(mock_get, max_results):
    assert fetch_most_popular(FAKE_KEY, "gb", max_results) == []
    assert mock_get.call_args.kwargs["params"]["regionCode"] == "GB"
    assert mock_get.call_args.kwargs["params"]["maxResults"] == max_results


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"api_key": ""}, "Missing YOUTUBE_API_KEY"),
        ({"api_key": "   "}, "Missing YOUTUBE_API_KEY"),
        ({"max_results": 0}, "maxResults"),
        ({"max_results": 51}, "maxResults"),
        ({"max_results": True}, "maxResults"),
        ({"region_code": "USA"}, "regionCode"),
        ({"region_code": "12"}, "regionCode"),
    ],
)
def test_invalid_configuration_does_not_send_request(mock_get, options, message):
    with pytest.raises(YouTubeError, match=message):
        fetch_most_popular(**{"api_key": FAKE_KEY, **options})
    mock_get.assert_not_called()


@pytest.mark.parametrize(
    ("failure", "message"),
    [(httpx.ReadTimeout, "timed out"), (httpx.ConnectError, "network connection")],
)
def test_network_errors_do_not_expose_secrets(mock_get, failure, message):
    mock_get.side_effect = failure(f"Request failed: {API_URL}?key={FAKE_KEY}")
    with pytest.raises(YouTubeError, match=message) as exc:
        fetch_most_popular(FAKE_KEY)
    assert FAKE_KEY not in str(exc.value)
    assert API_URL not in str(exc.value)


@pytest.mark.parametrize(
    ("status", "reason", "message"),
    [
        (400, "videoChartNotFound", "unsupported or unavailable"),
        (403, "quotaExceeded", "quota is exhausted"),
        (403, "dailyLimitExceeded", "quota is exhausted"),
        (403, "accessNotConfigured", "HTTP 403"),
        (400, "keyInvalid", "rejected the API key"),
        (429, "rateLimitExceeded", "rate limit"),
        (503, "backendError", "HTTP 503"),
    ],
)
def test_api_errors_are_clear_and_safe(mock_get, status, reason, message):
    mock_get.return_value = httpx.Response(
        status,
        json={"error": {"message": FAKE_KEY, "errors": [{"reason": reason}]}},
    )
    with pytest.raises(YouTubeError, match=message) as exc:
        fetch_most_popular(FAKE_KEY)
    assert FAKE_KEY not in str(exc.value)


@pytest.mark.parametrize("body", [b"not JSON", b'{"error": {"errors": null}}'])
def test_malformed_error_body_keeps_http_status(mock_get, body):
    mock_get.return_value = httpx.Response(403, content=body)
    with pytest.raises(YouTubeError, match="HTTP 403"):
        fetch_most_popular(FAKE_KEY)


def test_non_json_success_response(mock_get):
    mock_get.return_value = httpx.Response(200, text="not JSON")
    with pytest.raises(YouTubeError, match="invalid JSON"):
        fetch_most_popular(FAKE_KEY)


@pytest.mark.parametrize("body", [None, [], {}, {"items": {}}, {"items": [None]}])
def test_invalid_response_structure(mock_get, body):
    mock_get.return_value = httpx.Response(200, json=body)
    with pytest.raises(YouTubeError, match="invalid"):
        fetch_most_popular(FAKE_KEY)


@pytest.mark.parametrize(
    ("field", "value"),
    [("snippet", {}), ("snippet", None), ("id", 123), ("status", {"embeddable": "false"})],
)
def test_invalid_video_fields(mock_get, video_item, field, value):
    video_item[field] = value
    mock_get.return_value = httpx.Response(200, json={"items": [video_item]})
    with pytest.raises(YouTubeError, match="invalid"):
        fetch_most_popular(FAKE_KEY)


@pytest.fixture
def probe(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", FAKE_KEY)
    # Never read the developer's real .env during tests.
    monkeypatch.setattr("dotenv.load_dotenv", Mock())
    monkeypatch.setattr(sys, "argv", ["probe_youtube.py"])
    script = Path(__file__).resolve().parents[1] / "scripts" / "probe_youtube.py"
    return runpy.run_path(str(script))["main"]


@pytest.mark.parametrize("embeddable", [False, True])
def test_cli_output(probe, mock_get, video_item, capsys, monkeypatch, embeddable):
    video_item["status"]["embeddable"] = embeddable
    mock_get.return_value = httpx.Response(200, json={"items": [video_item]})
    monkeypatch.setattr(
        sys, "argv", ["probe_youtube.py", "--region-code", "GB", "--max-results", "5"]
    )
    assert probe() == 0
    output = capsys.readouterr()
    assert output.out == (
        "Video ID: sample-id\n"
        "Title: Example title\n"
        "Channel: Example channel\n"
        "Published: 2026-01-01T12:00:00Z\n"
        "Watch URL: https://www.youtube.com/watch?v=sample-id\n"
        f"Embeddable: {'yes' if embeddable else 'no'}\n\n"
    )
    assert output.err == ""
    assert mock_get.call_args.kwargs["params"]["regionCode"] == "GB"
    assert mock_get.call_args.kwargs["params"]["maxResults"] == 5


def test_cli_empty_results(probe, capsys):
    assert probe() == 0
    assert "No videos returned" in capsys.readouterr().out


def test_cli_missing_key(probe, mock_get, capsys, monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY")
    assert probe() == 1
    output = capsys.readouterr()
    assert "Missing YOUTUBE_API_KEY" in output.err
    assert output.out == ""
    mock_get.assert_not_called()


def test_cli_http_failure_hides_raw_body(probe, mock_get, capsys):
    mock_get.return_value = httpx.Response(403, text=f"Private server message: {FAKE_KEY}")
    assert probe() == 1
    output = capsys.readouterr()
    assert "HTTP 403" in output.err
    assert FAKE_KEY not in output.err
    assert "Private server message" not in output.err
    assert "Traceback" not in output.err
    assert output.out == ""
