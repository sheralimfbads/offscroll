"""Wikipedia pageviews. Project policy: retain raw responses for 90 days."""

import logging
import time
import unicodedata
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from offscroll.connectors._base import ConnectorError, ParseResult, RawResponse, Record
from offscroll.connectors._http import SourceHTTPError, request_json

BASE_URL = "https://wikimedia.org"
PREFIX = "/api/rest_v1/metrics/pageviews"
logger = logging.getLogger(__name__)
NAMESPACES = {
    "special",
    "talk",
    "user",
    "user_talk",
    "wikipedia",
    "wikipedia_talk",
    "file",
    "file_talk",
    "mediawiki",
    "mediawiki_talk",
    "template",
    "template_talk",
    "help",
    "help_talk",
    "category",
    "category_talk",
    "portal",
    "portal_talk",
    "draft",
    "draft_talk",
    "module",
    "module_talk",
    "media",
    "timedtext",
    "book",
    "book_talk",
}


def normalize_title(title: str) -> str:
    return unicodedata.normalize("NFC", title.strip().replace(" ", "_"))


def is_article(title: str) -> bool:
    return bool(title) and title != "Main_Page" and title.split(":", 1)[0].lower() not in NAMESPACES


class Article(BaseModel):
    model_config = ConfigDict(strict=True, hide_input_in_errors=True)
    article: str = Field(min_length=1)
    views: int = Field(ge=0, le=2**63 - 1)


class DailyViews(Article):
    timestamp: str = Field(pattern=r"^\d{10}$")


def top_articles(payload: dict[str, object]) -> tuple[list[Article], int]:
    items = payload.get("items")
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        raise ConnectorError("Wikipedia returned an invalid daily top envelope.")
    articles = items[0].get("articles")
    if not isinstance(articles, list):
        raise ConnectorError("Wikipedia returned no daily article list.")
    valid = []
    rejected = 0
    for raw in articles:
        try:
            article = Article.model_validate(raw)
        except ValidationError:
            rejected += 1
            continue
        if is_article(normalize_title(article.article)):
            valid.append(article)
    return valid, rejected


def parse(payload: dict[str, object], *, min_points: int = 20) -> ParseResult:
    """Top pages choose candidates; a complete 35-day series creates one topic."""
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ConnectorError("Wikipedia returned no pageview data.")
    if isinstance(items[0], dict) and "articles" in items[0]:
        articles, rejected = top_articles(payload)
        return ParseResult([], len(articles) + rejected, rejected)
    try:
        days = sorted(
            (DailyViews.model_validate(item) for item in items), key=lambda d: d.timestamp
        )
        dates = [datetime.strptime(d.timestamp, "%Y%m%d%H").replace(tzinfo=UTC) for d in days]
        title = normalize_title(days[0].article)
        if (
            len(days) != 35
            or any(normalize_title(d.article) != title for d in days)
            or dates != [dates[0] + timedelta(days=i) for i in range(35)]
            or not is_article(title)
        ):
            return ParseResult([], 1, 1)
        weekly = sum(d.views for d in days[-7:])
        baseline = sum(d.views for d in days[:28]) / 28
        if weekly > 2**63 - 1:
            return ParseResult([], 1, 1)
    except ValidationError, ValueError, OverflowError:
        return ParseResult([], 1, 1)
    return ParseResult(
        [
            Record(
                external_id=title,
                kind="topic",
                title=title.replace("_", " "),
                url="https://en.wikipedia.org/wiki/" + quote(title, safe=""),
                discussion_url=None,
                domain="en.wikipedia.org",
                author=None,
                # Topics have no publication date here: this is the end of the observation window.
                published_at=dates[-1] + timedelta(days=1),
                views=weekly,
                metadata={
                    "window_start": dates[-7].date().isoformat(),
                    "window_end": dates[-1].date().isoformat(),
                    "published_at_semantics": "observation_window_end",
                    "baseline_daily_views": baseline,
                    "baseline_days": 28,
                    "spike_ratio": (weekly / 7 / baseline) if baseline else None,
                    "attribution": "Wikimedia Analytics API (CC0 1.0)",
                },
            )
        ],
        1,
        0,
    )


class WikipediaConnector:
    source = "wikipedia"
    display_name = "Wikipedia"
    raw_retention_days = 90
    notes = "Project policy: raw pageview responses retained for 90 days."
    parse = staticmethod(parse)

    def fetch(
        self,
        client: httpx.Client,
        *,
        min_points: int = 20,
        page_cap: int = 5,
        end_date: date | None = None,
    ) -> list[RawResponse]:
        end = end_date or datetime.now(UTC).date() - timedelta(days=1)
        pages: list[RawResponse] = []
        requested = False

        def get(path: str) -> dict[str, object]:
            nonlocal requested
            if requested:
                time.sleep(1)  # Serial requests, at most 60/minute before network latency.
            requested = True
            payload = request_json(client, BASE_URL + path)
            pages.append(RawResponse(path, datetime.now(UTC), 200, payload, parse(payload).fetched))
            return payload

        totals: dict[str, int] = defaultdict(int)
        missing_days = 0
        for offset in range(6, -1, -1):
            day = end - timedelta(days=offset)
            try:
                payload = get(f"{PREFIX}/top/en.wikipedia.org/all-access/{day:%Y/%m/%d}")
            except SourceHTTPError as exc:
                if exc.status_code != 404:
                    raise
                # Discovery only: never substitute zero for missing article metrics.
                missing_days += 1
                logger.warning("event=wikipedia_discovery_missing date=%s http_status=404", day)
                continue
            articles, _ = top_articles(payload)
            for article in articles:
                totals[normalize_title(article.article)] += article.views
        if missing_days > 1:
            raise ConnectorError("Wikipedia requires at least six of seven daily discovery lists.")
        if missing_days:
            logger.warning("event=wikipedia_discovery_coverage available_days=6 expected_days=7")
        candidates = sorted(totals, key=lambda title: (-totals[title], title))[:60]
        if not candidates:
            raise ConnectorError("Wikipedia returned no article candidates.")
        start = end - timedelta(days=34)
        for title in candidates:
            # One request supplies exact 7-day views and the disjoint 28-day baseline.
            get(
                f"{PREFIX}/per-article/en.wikipedia.org/all-access/user/"
                f"{quote(title, safe='')}/daily/{start:%Y%m%d}00/{end:%Y%m%d}00"
            )
        return pages


connector = WikipediaConnector()
