"""Fetch one page of popular YouTube video metadata."""

from dataclasses import dataclass

import httpx

API_URL = "https://www.googleapis.com/youtube/v3/videos"


class YouTubeError(Exception):
    """A configuration, network, or API failure safe to display to the user."""


@dataclass
class Video:
    id: str
    title: str
    channel: str
    published_at: str
    embeddable: bool

    @property
    def watch_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.id}"


def fetch_most_popular(
    api_key: str, region_code: str = "US", max_results: int = 10
) -> list[Video]:
    """Make one GET request; return only the metadata needed by the probe."""
    if not api_key.strip():
        raise YouTubeError("Missing YOUTUBE_API_KEY. Set it in .env or your environment.")
    region_code = region_code.strip().upper()
    if len(region_code) != 2 or not region_code.isascii() or not region_code.isalpha():
        raise YouTubeError("regionCode must be a two-letter country code, such as US.")
    if type(max_results) is not int or not 1 <= max_results <= 50:
        raise YouTubeError("maxResults must be an integer between 1 and 50.")

    try:
        response = httpx.get(
            API_URL,
            params={
                "key": api_key.strip(),
                "part": "snippet,status",
                "chart": "mostPopular",
                "regionCode": region_code,
                "maxResults": max_results,
            },
            timeout=10.0,
        )
    except httpx.TimeoutException:
        raise YouTubeError("YouTube request timed out. Try again later.") from None
    except httpx.RequestError:
        # HTTP exceptions can contain the URL, including the API key.
        raise YouTubeError("Could not reach YouTube. Check your network connection.") from None

    if not response.is_success:
        raise YouTubeError(_api_error_message(response))
    try:
        data = response.json()
    except ValueError:
        raise YouTubeError("YouTube returned an invalid JSON response.") from None
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise YouTubeError("YouTube returned an invalid response: expected an items list.")
    return [_parse_video(item) for item in data["items"]]


def _parse_video(item: object) -> Video:
    """Reject incomplete metadata instead of inventing missing values."""
    if not isinstance(item, dict):
        raise YouTubeError("YouTube returned an invalid video item: expected an object.")
    try:
        video = Video(
            id=item["id"],
            title=item["snippet"]["title"],
            channel=item["snippet"]["channelTitle"],
            published_at=item["snippet"]["publishedAt"],
            embeddable=item["status"]["embeddable"],
        )
    except (KeyError, TypeError):
        raise YouTubeError("YouTube returned an invalid or incomplete video item.") from None
    text_fields = (video.id, video.title, video.channel, video.published_at)
    if not all(isinstance(value, str) and value.strip() for value in text_fields):
        raise YouTubeError("YouTube returned invalid video text fields.")
    if not isinstance(video.embeddable, bool):
        raise YouTubeError("YouTube returned an invalid embeddable status.")
    return video


def _api_error_message(response: httpx.Response) -> str:
    """Use known error reasons; never expose response bodies or request URLs."""
    try:
        data = response.json()
    except ValueError:
        data = {}
    error = data.get("error") if isinstance(data, dict) else None
    details = error.get("errors") if isinstance(error, dict) else None
    reasons = set()
    if isinstance(details, list):
        for detail in details:
            if isinstance(detail, dict) and isinstance(detail.get("reason"), str):
                reasons.add(detail["reason"])

    if "videoChartNotFound" in reasons:
        return (
            "The mostPopular chart is unsupported or unavailable for this region. "
            "Try another region."
        )
    if reasons & {"quotaExceeded", "dailyLimitExceeded"}:
        return (
            "YouTube API quota is exhausted. "
            "Check your Google Cloud quota or wait for it to reset."
        )
    if reasons & {"keyInvalid", "keyExpired"}:
        return (
            "YouTube rejected the API key. "
            "Check YOUTUBE_API_KEY in your local configuration."
        )
    if response.status_code == 429 or reasons & {"rateLimitExceeded", "userRateLimitExceeded"}:
        return "YouTube API rate limit reached. Wait before trying again."
    if response.status_code == 403:
        return (
            "YouTube denied access (HTTP 403). Check that YouTube Data API v3 is enabled, "
            "and review your API key restrictions and quota in Google Cloud."
        )
    return (
        f"YouTube API request failed (HTTP {response.status_code}). "
        "Check configuration or try again later."
    )
