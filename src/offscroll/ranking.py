"""Deterministic HN/Wikipedia scoring and clustering; YouTube never enters this module."""

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class DigestError(Exception):
    """Code-owned message safe for the CLI."""


class RankingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    hn_score_weight: float = Field(default=0.6, ge=0, le=1)
    hn_comments_weight: float = Field(default=0.4, ge=0, le=1)
    wiki_views_weight: float = Field(default=0.5, ge=0, le=1)
    wiki_spike_weight: float = Field(default=0.5, ge=0, le=1)
    jaccard_threshold: float = Field(default=0.5, gt=0, le=1)
    corroboration_step: float = Field(default=0.15, ge=0, le=0.3)
    corroboration_cap: float = Field(default=1.3, ge=1, le=1.3)
    hackernews_slots: int = Field(default=6, ge=1, le=6)
    wikipedia_slots: int = Field(default=5, ge=1, le=5)
    youtube_slots: int = Field(default=4, ge=1, le=4)
    per_domain: int = Field(default=2, ge=1, le=2)

    @model_validator(mode="after")
    def normalized_weights(self) -> RankingConfig:
        if not math.isclose(self.hn_score_weight + self.hn_comments_weight, 1) or not math.isclose(
            self.wiki_views_weight + self.wiki_spike_weight, 1
        ):
            raise ValueError("Each source's weights must sum to one.")
        return self


def load_ranking(path: Path) -> RankingConfig:
    try:
        return RankingConfig.model_validate(yaml.safe_load(path.read_text()))
    except OSError, UnicodeError, yaml.YAMLError, ValidationError:
        raise DigestError("Invalid ranking YAML configuration.") from None


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime


def digest_window(now: datetime, week: str | None = None) -> Window:
    if now.tzinfo is None:
        raise DigestError("Digest time must include a timezone.")
    now = now.astimezone(UTC)
    if week is None:
        return Window(now - timedelta(days=7), now)
    if not re.fullmatch(r"\d{4}-W\d{2}", week):
        raise DigestError("Use an ISO week such as 2026-W46.")
    try:
        year, number = week.split("-W")
        start = datetime.fromisocalendar(int(year), int(number), 1).replace(tzinfo=UTC)
    except ValueError:
        raise DigestError("Invalid ISO week.") from None
    if start > now:
        raise DigestError("Cannot build a future week.")
    return Window(start, start + timedelta(days=7))


@dataclass(frozen=True)
class Candidate:
    item_id: int
    source: Literal["hackernews", "wikipedia"]
    external_id: str
    title: str
    url: str | None
    domain: str | None
    published_at: datetime
    score: int | None = None
    comments: int | None = None
    views: int | None = None
    spike_ratio: float | None = None
    discussion_url: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        # Runtime boundary also protects callers that do not use static typing.
        if self.source not in {"hackernews", "wikipedia"}:
            raise DigestError("Only Hacker News and Wikipedia can enter shared ranking.")


@dataclass
class Ranked:
    item: Candidate
    final_score: float
    breakdown: dict[str, object]
    also_covered: list[Candidate] = field(default_factory=list)


def percentiles(values: list[float | int | None]) -> list[float]:
    """Average rank / (n - 1); missing = 0, singleton = 1, tied pool = 0.5."""
    valid = sorted(v for v in values if v is not None and math.isfinite(v))
    if not valid:
        return [0.0] * len(values)
    ranks: dict[float, float] = {}
    offset = 0
    for value, count in sorted(Counter(valid).items()):
        ranks[value] = (offset + (count - 1) / 2) / (len(valid) - 1) if len(valid) > 1 else 1.0
        offset += count
    return [ranks.get(v, 0.0) if v is not None else 0.0 for v in values]


STOP_WORDS = frozenset({"a", "an", "the", "of", "and", "or", "to", "in", "on", "for", "with"})


def title_tokens(title: str) -> set[str]:
    text = unicodedata.normalize("NFKC", title).casefold()
    return set(re.findall(r"[^\W_]+", text)) - STOP_WORDS


def canonical_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return None
        return urlunsplit(
            ("https", parts.hostname.removeprefix("www."), parts.path.rstrip("/"), parts.query, "")
        )
    except ValueError:
        return None


def related(left: Candidate, right: Candidate, threshold: float) -> bool:
    if left.source == right.source:
        return False
    a, b = title_tokens(left.title), title_tokens(right.title)
    similarity = len(a & b) / len(a | b) if a | b else 0.0
    url = canonical_url(left.url)
    # Sharing a publisher is only supporting context, never enough by itself.
    shared_domain = left.domain is not None and left.domain == right.domain
    return bool(
        (url and url == canonical_url(right.url))
        or similarity >= threshold
        or (shared_domain and len(a & b) >= 2 and similarity >= threshold / 2)
    )


def _key(row: Ranked) -> tuple[float, float, str, str]:
    return (
        -row.final_score,
        -row.item.published_at.timestamp(),
        row.item.source,
        row.item.external_id,
    )


def rank_candidates(items: list[Candidate], config: RankingConfig) -> list[Ranked]:
    ranked = []
    for source in ("hackernews", "wikipedia"):
        pool = sorted((i for i in items if i.source == source), key=lambda i: i.external_id)
        first = percentiles([i.score if source == "hackernews" else i.views for i in pool])
        second = percentiles(
            [i.comments if source == "hackernews" else i.spike_ratio for i in pool]
        )
        weights = (
            (config.hn_score_weight, config.hn_comments_weight)
            if source == "hackernews"
            else (config.wiki_views_weight, config.wiki_spike_weight)
        )
        for item, a, b in zip(pool, first, second, strict=True):
            momentum = weights[0] * a + weights[1] * b
            ranked.append(
                Ranked(
                    item,
                    momentum,
                    {"momentum": momentum, "percentiles": [a, b], "weights": list(weights)},
                )
            )
    # Greedy complete-link groups avoid a chain of weak matches merging unrelated topics.
    clusters: list[list[Ranked]] = []
    for row in sorted(ranked, key=_key):
        for cluster in clusters:
            if all(related(row.item, other.item, config.jaccard_threshold) for other in cluster):
                cluster.append(row)
                break
        else:
            clusters.append([row])
    representatives = []
    for cluster in clusters:
        sources = len({row.item.source for row in cluster})
        multiplier = min(config.corroboration_cap, 1 + config.corroboration_step * (sources - 1))
        best = sorted(cluster, key=_key)[0]
        best.final_score *= multiplier
        best.breakdown.update({"distinct_sources": sources, "multiplier": multiplier})
        best.also_covered = [row.item for row in sorted(cluster, key=_key) if row is not best]
        representatives.append(best)
    return sorted(representatives, key=_key)


def select_lanes(ranked: list[Ranked], config: RankingConfig) -> dict[str, list[Ranked]]:
    lanes: dict[str, list[Ranked]] = {"hackernews": [], "wikipedia": []}
    domains: Counter[str] = Counter()
    for row in sorted(ranked, key=_key):
        lane = lanes[row.item.source]
        cap = config.hackernews_slots if row.item.source == "hackernews" else config.wikipedia_slots
        # Wikipedia is the source, not an external publisher; a domain cap would
        # otherwise reduce its entire lane to two topics.
        domain = row.item.domain if row.item.source == "hackernews" else None
        if len(lane) >= cap or (domain and domains[domain] >= config.per_domain):
            continue
        lane.append(row)
        if domain:
            domains[domain] += 1
    return lanes
