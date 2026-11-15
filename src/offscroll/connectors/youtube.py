"""Curated YouTube metadata only; all API-derived data expires within 30 days."""

import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlencode

import httpx
import yaml
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    field_validator,
)
from sqlalchemy import Engine, text

from offscroll.config import SourceSettings
from offscroll.connectors._base import ConnectorError, ParseResult, RawResponse, Record
from offscroll.connectors._http import request_json
from offscroll.quota import YouTubeQuota

BASE_URL = "https://www.googleapis.com"
PREFIX = "/youtube/v3/"
logger = logging.getLogger(__name__)
VideoId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{11}$")]
ChannelId = Annotated[str, Field(pattern=r"^UC[A-Za-z0-9_-]{22}$")]


class MissingKeyError(ConnectorError):
    """YouTube was enabled but no exported API key is available."""


class ChannelConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)
    handle: str = Field(pattern=r"^@[\w.-]{3,30}$")
    category: Literal["science", "technology", "world", "economics", "culture"]
    active: bool = True


class ChannelFile(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)
    channels: list[ChannelConfig] = Field(min_length=1, max_length=100)

    @field_validator("channels")
    @classmethod
    def unique_handles(cls, channels: list[ChannelConfig]) -> list[ChannelConfig]:
        if len({c.handle.lower() for c in channels}) != len(channels):
            raise ValueError("Channel handles must be unique.")
        return channels


def load_channels(path: Path) -> list[ChannelConfig]:
    try:
        config = ChannelFile.model_validate(yaml.safe_load(path.read_text()))
    except OSError, UnicodeError, yaml.YAMLError, ValidationError:
        raise ConnectorError(
            "Invalid YouTube channel configuration; check the YAML file."
        ) from None
    return config.channels


class Snippet(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True, str_strip_whitespace=True)
    title: str = Field(min_length=1, strict=True)
    channelId: ChannelId
    channelTitle: str = Field(min_length=1, strict=True)
    publishedAt: AwareDatetime
    thumbnails: dict[str, dict[str, object]] = Field(default_factory=dict)


class Statistics(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    viewCount: int | None = Field(default=None, ge=0, le=2**63 - 1)
    likeCount: int | None = Field(default=None, ge=0, le=2**63 - 1)
    commentCount: int | None = Field(default=None, ge=0, le=2**63 - 1)

    @field_validator("viewCount", "likeCount", "commentCount", mode="before")
    @classmethod
    def decimal_counts(cls, value: object) -> object:
        if (
            value is None
            or type(value) is int
            or (isinstance(value, str) and value.isascii() and value.isdecimal())
        ):
            return value
        raise ValueError("Expected a nonnegative integer count.")


class VideoStatus(BaseModel):
    model_config = ConfigDict(strict=True, hide_input_in_errors=True)
    embeddable: bool
    privacyStatus: Literal["public", "private", "unlisted"]


class Video(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    id: VideoId
    snippet: Snippet
    statistics: Statistics
    status: VideoStatus
    contentDetails: dict[str, object]


def parse(payload: dict[str, object], *, min_points: int = 20) -> ParseResult:
    items = payload.get("items")
    if not isinstance(items, list):
        raise ConnectorError("YouTube returned no items list.")
    if payload.get("kind") in {"youtube#channelListResponse", "youtube#playlistItemListResponse"}:
        return ParseResult([], 0, 0)
    if payload.get("kind") != "youtube#videoListResponse":
        raise ConnectorError("YouTube returned an unexpected resource kind.")
    records = []
    rejected = 0
    for raw in items:
        try:
            video = Video.model_validate(raw)
            if video.status.privacyStatus != "public":
                continue
            thumbnails = {}
            for size, thumbnail in video.snippet.thumbnails.items():
                value = thumbnail["url"]
                if not isinstance(value, str):
                    raise ValueError("Invalid thumbnail URL.")
                url = HttpUrl(value)
                if (
                    url.scheme != "https"
                    or url.username
                    or url.password
                    or not (url.host or "").endswith(".ytimg.com")
                ):
                    raise ValueError("Unexpected thumbnail URL.")
                thumbnails[size] = value
        except ValidationError, ValueError, KeyError, TypeError:
            rejected += 1
            continue
        records.append(
            Record(
                external_id=video.id,
                kind="video",
                title=video.snippet.title.strip(),
                url=f"https://www.youtube.com/watch?v={video.id}",
                discussion_url=None,
                domain="youtube.com",
                author=video.snippet.channelTitle,
                published_at=video.snippet.publishedAt,
                views=video.statistics.viewCount,
                likes=video.statistics.likeCount,
                comments=video.statistics.commentCount,
                metadata={
                    "channel_id": video.snippet.channelId,
                    "embeddable": video.status.embeddable,
                    "thumbnails": thumbnails,
                    "content_details": video.contentDetails,
                    "attribution": "YouTube",
                },
            )
        )
    return ParseResult(records, len(items), rejected)


class Upload(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    videoId: VideoId
    videoPublishedAt: AwareDatetime


class ChannelSnippet(BaseModel):
    title: str = Field(min_length=1)


class RelatedPlaylists(BaseModel):
    uploads: str = Field(pattern=r"^[A-Za-z0-9_-]+$")


class ChannelDetails(BaseModel):
    relatedPlaylists: RelatedPlaylists


class Channel(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    id: ChannelId
    snippet: ChannelSnippet
    contentDetails: ChannelDetails


class YouTubeConnector:
    source = "youtube"
    display_name = "YouTube"
    raw_retention_days = 30
    notes = "Delete or refresh API-derived raw and core data within 30 days."
    parse = staticmethod(parse)

    def __init__(self, engine: Engine | None, settings: SourceSettings | None = None) -> None:
        self.engine = engine
        self.settings = settings or SourceSettings()

    def fetch(
        self,
        client: httpx.Client,
        *,
        min_points: int = 20,
        page_cap: int = 5,
    ) -> list[RawResponse]:
        key = self.settings.youtube_api_key
        if key is None or not key.get_secret_value().strip():
            raise MissingKeyError("Export YOUTUBE_API_KEY before collecting YouTube.")
        if self.engine is None:
            raise ConnectorError("YouTube collection requires database-backed quota accounting.")
        configs = load_channels(self.settings.youtube_channels_file)
        quota = YouTubeQuota(self.engine)
        pages: list[RawResponse] = []
        now = datetime.now(UTC)

        def get(resource: str, params: dict[str, str | int]) -> dict[str, object]:
            if pages:
                time.sleep(0.5)
            path = PREFIX + resource
            payload = request_json(
                client,
                BASE_URL + path,
                params=params,
                headers={"X-Goog-Api-Key": key.get_secret_value()},
                reserve=quota.reserve,
            )
            if not isinstance(payload.get("items"), list):
                raise ConnectorError("YouTube returned no items list.")
            items = payload["items"]
            count = len(items) if resource == "videos" and isinstance(items, list) else 0
            pages.append(
                RawResponse(path + "?" + urlencode(params), datetime.now(UTC), 200, payload, count)
            )
            return payload

        try:
            with self.engine.begin() as connection:
                # Config is authoritative: removed or disabled entries are not fetched.
                connection.execute(text("UPDATE core.youtube_channels SET active = false"))
            ids: set[str] = set()
            for config in configs:
                if not config.active:
                    continue
                with self.engine.connect() as connection:
                    cached = (
                        connection.execute(
                            text("""
                        SELECT channel_id, uploads_playlist_id FROM core.youtube_channels
                        WHERE handle = :handle AND refreshed_at > now() - interval '1 day'
                    """),
                            {"handle": config.handle},
                        )
                        .mappings()
                        .first()
                    )
                if cached is None:
                    payload = get(
                        "channels",
                        {
                            "part": "snippet,contentDetails",
                            "forHandle": config.handle,
                        },
                    )
                    items = payload["items"]
                    if not isinstance(items, list) or len(items) != 1:
                        raise ConnectorError(
                            "A configured YouTube handle did not resolve uniquely."
                        )
                    try:
                        channel = Channel.model_validate(items[0])
                    except ValidationError:
                        raise ConnectorError("YouTube returned invalid channel metadata.") from None
                    playlist = channel.contentDetails.relatedPlaylists.uploads
                    with self.engine.begin() as connection:
                        # Re-resolving a changed handle must not leave its stale mapping behind.
                        connection.execute(
                            text("""
                            DELETE FROM core.youtube_channels
                            WHERE handle = :handle AND channel_id != :id
                        """),
                            {"handle": config.handle, "id": channel.id},
                        )
                        connection.execute(
                            text("""
                            INSERT INTO core.youtube_channels
                                (channel_id, handle, title, uploads_playlist_id,
                                 category, active, refreshed_at)
                            VALUES (:id, :handle, :title, :playlist, :category, true, :at)
                            ON CONFLICT (channel_id) DO UPDATE SET handle = EXCLUDED.handle,
                                title = EXCLUDED.title,
                                uploads_playlist_id = EXCLUDED.uploads_playlist_id,
                                category = EXCLUDED.category, active = true,
                                refreshed_at = EXCLUDED.refreshed_at
                        """),
                            {
                                "id": channel.id,
                                "handle": config.handle,
                                "title": channel.snippet.title,
                                "playlist": playlist,
                                "category": config.category,
                                "at": now,
                            },
                        )
                else:
                    playlist = cached["uploads_playlist_id"]
                    with self.engine.begin() as connection:
                        connection.execute(
                            text("""
                            UPDATE core.youtube_channels SET active = true, category = :category
                            WHERE channel_id = :id
                        """),
                            {"id": cached["channel_id"], "category": config.category},
                        )
                payload = get(
                    "playlistItems",
                    {
                        "part": "contentDetails",
                        "playlistId": playlist,
                        "maxResults": 10,
                    },
                )
                uploads = payload["items"]
                if not isinstance(uploads, list):
                    raise ConnectorError("YouTube returned an invalid upload list.")
                for raw in uploads:
                    try:
                        if not isinstance(raw, dict):
                            raise ValueError("Invalid upload.")
                        upload = Upload.model_validate(raw.get("contentDetails"))
                    except ValidationError, ValueError:
                        # Discovery corruption must not silently produce a successful empty run.
                        raise ConnectorError("YouTube returned invalid upload metadata.") from None
                    if now - timedelta(days=14) <= upload.videoPublishedAt <= now:
                        ids.add(upload.videoId)
            ordered = sorted(ids)
            for start in range(0, len(ordered), 50):
                get(
                    "videos",
                    {
                        "part": "snippet,statistics,contentDetails,status",
                        "id": ",".join(ordered[start : start + 50]),
                    },
                )
            return pages
        finally:
            logger.info("event=quota_usage source=youtube units=%s", quota.units)


def create_connector(engine: Engine | None = None) -> YouTubeConnector:
    return YouTubeConnector(engine)
