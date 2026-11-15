"""Hacker News via Algolia. Project retention policy: raw responses last 90 days."""

import logging
import secrets
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, field_validator

from offscroll.connectors._base import ConnectorError, ParseResult, RawResponse, Record

logger = logging.getLogger(__name__)
API_URL = "https://hn.algolia.com/api/v1/search_by_date"
USER_AGENT = "Offscroll/0.1 (weekly digest; +https://github.com/sheralimfbads/offscroll/issues)"


class Hit(BaseModel):
    model_config = ConfigDict(strict=True, str_strip_whitespace=True, hide_input_in_errors=True)

    objectID: str = Field(pattern=r"^[1-9][0-9]*$")
    title: str = Field(min_length=1)
    created_at_i: int = Field(ge=0)
    points: int | None = Field(ge=0, le=2**63 - 1)
    num_comments: int | None = Field(ge=0, le=2**63 - 1)
    url: HttpUrl | None = None
    author: str | None = None

    @field_validator("url")
    @classmethod
    def reject_credentials(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is None:
            return None
        sensitive = {
            "key",
            "api_key",
            "apikey",
            "token",
            "access_token",
            "password",
            "secret",
            "signature",
            "sig",
            "auth",
            "authorization",
            "credential",
            "x-amz-signature",
            "x-amz-credential",
            "x-amz-security-token",
        }
        if (
            value.username
            or value.password
            or any(key.lower() in sensitive for key, _ in parse_qsl(value.query or ""))
        ):
            raise ValueError("Credential-bearing story URLs cannot be displayed.")
        return value


def parse(payload: dict[str, object], *, min_points: int = 20) -> ParseResult:
    """Validate hits; eligible records and rejected counts depend only on inputs."""
    hits = payload.get("hits")
    if not isinstance(hits, list):
        raise ConnectorError("HN payload has no hits list.")
    records = []
    rejected = 0
    for raw_hit in hits:
        try:
            hit = Hit.model_validate(raw_hit)
            published_at = datetime.fromtimestamp(hit.created_at_i, UTC)
        except ValidationError, ValueError, OverflowError, OSError:
            rejected += 1
            continue
        if hit.points is None or hit.points < min_points:
            continue
        url = str(hit.url) if hit.url else None
        host = urlsplit(url).hostname if url else None
        records.append(
            Record(
                external_id=hit.objectID,
                kind="story",
                title=hit.title,
                url=url,
                discussion_url=f"https://news.ycombinator.com/item?id={hit.objectID}",
                domain=host.removeprefix("www.") if host else None,
                author=hit.author,
                published_at=published_at,
                score=hit.points,
                comments=hit.num_comments,
            )
        )
    return ParseResult(records, fetched=len(hits), rejected=rejected)


def _request(client: httpx.Client, params: dict[str, str | int]) -> httpx.Response:
    for attempt in range(3):
        try:
            response = client.get(
                API_URL,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=httpx.Timeout(15, connect=5),
            )
        except httpx.TimeoutException:
            reason = "timeout"
        except httpx.RequestError:
            raise ConnectorError("HN network request failed.") from None
        else:
            if response.status_code == 200:
                return response
            if response.status_code != 429 and not 500 <= response.status_code < 600:
                raise ConnectorError(f"HN request rejected (HTTP {response.status_code}).")
            reason = f"http_{response.status_code}"
        if attempt < 2:
            logger.warning(
                "event=retry source=hackernews attempt=%s reason=%s", attempt + 1, reason
            )
            time.sleep(2**attempt + secrets.randbelow(250) / 1000)
    raise ConnectorError("HN request failed after 3 attempts.")


class HackerNewsConnector:
    source = "hackernews"
    display_name = "Hacker News"
    raw_retention_days = 90
    notes = "Project policy: purge raw API responses after 90 days."

    parse = staticmethod(parse)

    def fetch(
        self, client: httpx.Client, *, min_points: int = 20, page_cap: int = 5
    ) -> list[RawResponse]:
        if min_points < 0 or page_cap < 1:
            raise ConnectorError(
                "Minimum points must be nonnegative and page cap must be positive."
            )
        cutoff = int((datetime.now(UTC) - timedelta(days=7)).timestamp())
        pages: list[RawResponse] = []
        fetched = 0
        total = 0
        for page in range(page_cap):
            if page:
                time.sleep(0.5)
            # The points filter was verified with one live call on 2026-11-14.
            params: dict[str, str | int] = {
                "tags": "story",
                "numericFilters": f"created_at_i>{cutoff},points>={min_points}",
                "hitsPerPage": 1000,
                "page": page,
            }
            response = _request(client, params)
            try:
                payload = response.json()
            except ValueError:
                raise ConnectorError("HN returned invalid JSON.") from None
            if (
                not isinstance(payload, dict)
                or not isinstance(payload.get("hits"), list)
                or type(payload.get("nbHits")) is not int
                or payload["nbHits"] < 0
                or type(payload.get("nbPages")) is not int
                or payload["nbPages"] < 0
            ):
                raise ConnectorError("HN returned an invalid page envelope.")
            pages.append(
                RawResponse(
                    endpoint="/api/v1/search_by_date?" + urlencode(params),
                    fetched_at=datetime.now(UTC),
                    http_status=response.status_code,
                    payload=payload,
                    items_fetched=len(payload["hits"]),
                )
            )
            fetched += len(payload["hits"])
            total = max(total, payload["nbHits"])
            if not payload["hits"] or page + 1 >= payload["nbPages"]:
                break
        if total > fetched:
            logger.warning(
                "event=truncated source=hackernews nb_hits=%s fetched=%s page_cap=%s",
                total,
                fetched,
                page_cap,
            )
        return pages


connector = HackerNewsConnector()
