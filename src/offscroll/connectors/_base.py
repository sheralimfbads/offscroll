"""Small shared contract: fetch pages, then parse their payloads without I/O."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

import httpx


class ConnectorError(Exception):
    """A safe, fixed message describing a source failure."""


@dataclass(frozen=True)
class RawResponse:
    endpoint: str
    fetched_at: datetime
    http_status: int
    payload: dict[str, object]
    items_fetched: int = 0


@dataclass(frozen=True)
class Record:
    external_id: str
    kind: str
    title: str
    url: str | None
    discussion_url: str | None
    domain: str | None
    author: str | None
    published_at: datetime
    score: int | None = None
    comments: int | None = None
    views: int | None = None
    likes: int | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ParseResult:
    records: list[Record]
    fetched: int
    rejected: int


class Connector(Protocol):
    source: str
    display_name: str
    raw_retention_days: int
    notes: str

    def fetch(
        self, client: httpx.Client, *, min_points: int = 20, page_cap: int = 5
    ) -> list[RawResponse]: ...

    def parse(self, payload: dict[str, object], *, min_points: int = 20) -> ParseResult: ...
