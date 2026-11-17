import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest

from offscroll.config import SourceSettings
from offscroll.connectors._base import ConnectorError
from offscroll.connectors.youtube import (
    MissingKeyError,
    YouTubeConnector,
    YouTubeSourceError,
    load_channels,
    parse,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_video_counts_and_metadata_stay_api_provided():
    result = parse(json.loads((FIXTURES / "youtube_videos.json").read_text()))
    assert result.rejected == 0
    record = result.records[0]
    assert record.views == 100
    assert record.comments == 4
    assert record.likes is None
    assert record.metadata["embeddable"] is False
    assert record.metadata["channel_id"] == "UC" + "A" * 22
    assert record.metadata["thumbnails"]["default"].startswith("https://i.ytimg.com/")
    assert record.url == "https://www.youtube.com/watch?v=AAAAAAAAAAA"


@pytest.mark.parametrize("fault", ["count", "boolean", "title", "date", "thumbnail", "id"])
def test_invalid_video_is_rejected(fault):
    payload = json.loads((FIXTURES / "youtube_videos.json").read_text())
    item = payload["items"][0]
    if fault == "count":
        item["statistics"]["viewCount"] = -1
    elif fault == "boolean":
        item["statistics"]["viewCount"] = True
    elif fault == "title":
        item["snippet"]["title"] = "   "
    elif fault == "date":
        item["snippet"]["publishedAt"] = "2026-11-01T00:00:00"
    elif fault == "thumbnail":
        item["snippet"]["thumbnails"]["default"]["url"] = "https://example.com/image.jpg"
    else:
        item["id"] = "invalid"
    assert parse(payload).rejected == 1
    assert parse(payload).records == []


def test_source_settings_mask_key_and_validate_enabled_sources(monkeypatch):
    monkeypatch.delenv("OFFSCROLL_SOURCES", raising=False)
    key = uuid4().hex
    monkeypatch.setenv("YOUTUBE_API_KEY", key)
    settings = SourceSettings()
    assert key not in repr(settings)
    assert key not in str(settings)
    assert key not in settings.model_dump_json()
    assert settings.enabled_sources == ["hackernews", "wikipedia", "youtube"]


def test_missing_key_fails_before_requests(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _: pytest.fail("Unexpected HTTP"))
        ) as client,
        pytest.raises(MissingKeyError, match="Export YOUTUBE_API_KEY"),
    ):
        YouTubeConnector(None, SourceSettings()).fetch(client)


@pytest.mark.parametrize(
    "content",
    [
        "!!python/object/apply:os.system ['false']",
        "channels: [{handle: '@abc', category: science}, {handle: '@ABC', category: science}]",
        "channels: [{handle: '@abc', category: unknown}]",
        "channels: []",
    ],
)
def test_unsafe_or_invalid_channel_config_is_rejected(tmp_path, content):
    path = tmp_path / "channels.yaml"
    path.write_text(content)
    with pytest.raises(ConnectorError, match="Invalid YouTube channel configuration"):
        load_channels(path)


def test_curated_file_has_25_unique_candidates():
    assert len(load_channels(Path("config/youtube_channels.yaml"))) == 25


@pytest.fixture
def fetch_setup(tmp_path, monkeypatch):
    path = tmp_path / "channels.yaml"
    path.write_text("channels: [{handle: '@example', category: science}]")
    key = uuid4().hex
    settings = SourceSettings(youtube_api_key=key, youtube_channels_file=path)
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value.first.return_value = None
    charged = []

    class Quota:
        units = 0

        def __init__(self, engine, *, limit):
            assert limit == settings.youtube_run_limit

        def reserve(self):
            self.units += 1
            charged.append(1)

    monkeypatch.setattr("offscroll.connectors.youtube.YouTubeQuota", Quota)
    monkeypatch.setattr("offscroll.connectors.youtube.time.sleep", lambda _: None)
    return YouTubeConnector(engine, settings), key, charged, engine


def channel_payload(index=0):
    return {
        "kind": "youtube#channelListResponse",
        "items": [
            {
                "id": "UC" + str(index).zfill(22),
                "snippet": {"title": "Example"},
                "contentDetails": {"relatedPlaylists": {"uploads": "UU" + str(index).zfill(22)}},
            }
        ],
    }


def test_fetch_uses_header_auth_filters_old_uploads_and_lands_safe_endpoints(fetch_setup, caplog):
    connector, key, charged, _ = fetch_setup
    requests = []
    now = datetime.now(UTC)

    def respond(request):
        requests.append(request)
        assert request.headers["X-Goog-Api-Key"] == key
        assert key not in str(request.url)
        if request.url.path.endswith("/channels"):
            assert request.url.params["forHandle"] == "@example"
            return httpx.Response(200, json=channel_payload())
        if request.url.path.endswith("/playlistItems"):
            assert request.url.params["maxResults"] == "10"
            return httpx.Response(
                200,
                json={
                    "kind": "youtube#playlistItemListResponse",
                    "items": [
                        {
                            "contentDetails": {
                                "videoId": "AAAAAAAAAAA",
                                "videoPublishedAt": now.isoformat(),
                            }
                        },
                        {
                            "contentDetails": {
                                "videoId": "BBBBBBBBBBB",
                                "videoPublishedAt": (now - timedelta(days=15)).isoformat(),
                            }
                        },
                    ],
                },
            )
        assert request.url.params["id"] == "AAAAAAAAAAA"
        assert request.url.params["part"] == "snippet,statistics,contentDetails,status"
        return httpx.Response(200, json=json.loads((FIXTURES / "youtube_videos.json").read_text()))

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        pages = connector.fetch(client)
    assert len(requests) == len(charged) == len(pages) == 3
    assert pages[-1].items_fetched == 1
    assert all(key not in page.endpoint and "key=" not in page.endpoint for page in pages)
    assert key not in caplog.text


def test_channel_cache_avoids_resolution_request(fetch_setup):
    connector, _, charged, engine = fetch_setup
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value.first.return_value = {
        "channel_id": "UC" + "A" * 22,
        "uploads_playlist_id": "UU" + "A" * 22,
    }

    def respond(request):
        assert request.url.path.endswith("/playlistItems")
        return httpx.Response(200, json={"kind": "youtube#playlistItemListResponse", "items": []})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        connector.fetch(client)
    assert charged == [1]


def test_video_requests_batch_at_50(fetch_setup):
    connector, _, _, _ = fetch_setup
    connector.settings.youtube_channels_file.write_text(
        json.dumps(
            {"channels": [{"handle": f"@example{n}", "category": "science"} for n in range(6)]}
        )
    )
    batches = []

    def respond(request):
        if request.url.path.endswith("/channels"):
            return httpx.Response(
                200, json=channel_payload(int(request.url.params["forHandle"][-1]))
            )
        if request.url.path.endswith("/playlistItems"):
            channel = int(request.url.params["playlistId"][-1])
            return httpx.Response(
                200,
                json={
                    "kind": "youtube#playlistItemListResponse",
                    "items": [
                        {
                            "contentDetails": {
                                "videoId": str(channel * 10 + n).zfill(11),
                                "videoPublishedAt": (
                                    datetime.now(UTC) - timedelta(hours=1)
                                ).isoformat(),
                            }
                        }
                        for n in range(10)
                    ],
                },
            )
        batches.append(request.url.params["id"].split(","))
        return httpx.Response(200, json={"kind": "youtube#videoListResponse", "items": []})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        connector.fetch(client)
    assert [len(batch) for batch in batches] == [50, 10]


@pytest.mark.parametrize("cached,expected_units", [(False, 23), (True, 12)])
def test_twelfth_handle_failure_matches_cold_and_warm_cache_counts(
    fetch_setup, cached, expected_units
):
    connector, key, charged, engine = fetch_setup
    connector.settings.youtube_channels_file.write_text(
        json.dumps(
            {"channels": [{"handle": f"@example{n}", "category": "science"} for n in range(12)]}
        )
    )
    if cached:
        connection = engine.connect.return_value.__enter__.return_value
        connection.execute.return_value.mappings.return_value.first.side_effect = [
            {"channel_id": "UC" + str(n).zfill(22), "uploads_playlist_id": "UU" + str(n).zfill(22)}
            for n in range(11)
        ] + [None]

    def respond(request):
        if request.url.path.endswith("/channels"):
            handle = request.url.params["forHandle"]
            payload = {"kind": "youtube#channelListResponse", "items": []}
            if handle != "@example11":
                payload = channel_payload(int(handle.removeprefix("@example")))
            return httpx.Response(200, json=payload)
        return httpx.Response(200, json={"kind": "youtube#playlistItemListResponse", "items": []})

    with (
        httpx.Client(transport=httpx.MockTransport(respond)) as client,
        pytest.raises(YouTubeSourceError) as error,
    ):
        connector.fetch(client)
    assert str(error.value) == "youtube_handle_unresolved resource=channels channel_index=12"
    assert len(charged) == expected_units
    assert key not in str(error.value)
    assert key not in repr(error.value)


def test_http_failure_diagnostic_excludes_response_body_headers_and_url(fetch_setup):
    connector, key, charged, _ = fetch_setup
    response = httpx.Response(404, json={"error": {"message": f"private {key}"}})
    with (
        httpx.Client(transport=httpx.MockTransport(lambda _: response)) as client,
        pytest.raises(YouTubeSourceError) as error,
    ):
        connector.fetch(client)
    assert (
        str(error.value) == "youtube_http_error resource=channels channel_index=1 http_status=404"
    )
    assert key not in str(error.value)
    assert "private" not in str(error.value)
    assert charged == [1]


def test_invalid_upload_diagnostic_locates_the_playlist(fetch_setup):
    connector, key, _, _ = fetch_setup

    def respond(request):
        if request.url.path.endswith("/channels"):
            return httpx.Response(200, json=channel_payload())
        return httpx.Response(
            200,
            json={
                "kind": "youtube#playlistItemListResponse",
                "items": [{"contentDetails": {"bad": key}}],
            },
        )

    with (
        httpx.Client(transport=httpx.MockTransport(respond)) as client,
        pytest.raises(YouTubeSourceError) as error,
    ):
        connector.fetch(client)
    assert (
        str(error.value) == "youtube_invalid_upload_metadata resource=playlistItems channel_index=1"
    )
    assert key not in repr(error.value)


def test_title_and_thumbnail_are_preserved_exactly():
    payload = json.loads((FIXTURES / "youtube_videos.json").read_text())
    raw = payload["items"][0]
    raw["snippet"]["title"] = "  Exact API title  "
    result = parse(payload)
    assert result.records[0].title == raw["snippet"]["title"]
    assert result.records[0].metadata["privacy_status"] == "public"
    assert result.records[0].metadata["thumbnails"] == {
        size: data["url"] for size, data in raw["snippet"]["thumbnails"].items()
    }
