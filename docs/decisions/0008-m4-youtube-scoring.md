# 0008: Keep YouTube in an isolated digest lane

Status: accepted
Date: 2026-11-16

## Context

The owner rejected the earlier proposal to exclude YouTube and explicitly chose
this lane design on 2026-11-16. M3 was merged to `main` at `35429cb`; `m4-ranking`
was rebased onto it before implementation. This decision supersedes the exclusion
proposal and the original shared-scale YouTube formula in the M4 brief.

Official sources re-read on 2026-11-16:

- [Complying with YouTube's Developer Policies](https://developers.google.com/youtube/terms/developer-policies-guide),
  page last updated **2026-09-14 UTC**, retrieved **2026-11-16**. The guide gives
  examples of simple arithmetic using YouTube API data only, and prohibits mixing
  it with external data, modifying titles/thumbnails, and inferring categories.
- [YouTube branding guidelines](https://developers.google.com/youtube/terms/branding-guidelines),
  page last updated **2025-08-20 UTC**, retrieved **2026-11-16**. For the eventual
  graphical page, use an official unmodified YouTube logo beside the YouTube
  section, linked to YouTube content, with the required size/contrast/clear space.
  Do not imply YouTube endorses Offscroll. The CLI uses a literal YouTube heading;
  graphical branding belongs to the M5 page implementation.
- [Developer policies, III.E.4.h and III.L](https://developers.google.com/youtube/terms/developer-policies),
  retrieved **2026-11-16**. The broad derived-data wording and additional analytics
  permission route remain relevant; this decision is not a claim of API approval.

## Decision

Maintain three labelled lanes, ordered Hacker News, Wikipedia, YouTube for display.
There is no overall rank. Caps are 6 HN, 5 Wikipedia, and 4 YouTube; a short lane
is never filled from another. HN has at most two links per external publisher;
YouTube has at most one video per channel. Wikipedia's own domain is not treated
as an external publisher, so its five topic slots remain usable.

HN/Wikipedia alone enter percentile scoring, title/URL clustering, and the
cross-source multiplier. YouTube never contributes to their candidate pools,
clusters, score breakdowns, or "also covered by" lists.

Select recent public, embeddable YouTube videos by views divided by
`max(age_in_days, 1)` in SQL `ORDER BY`, using API view counts and publication
timestamps with the build clock as the age reference. No external engagement
signal is involved. The arithmetic result never leaves the SQL ordering operation:
no stored score, percentile, multiplier, derived metric display, or derived
channel category. SQL ties use publication time then video ID. Missing view counts
are not invented. Eligibility requires explicit stored public/embeddable status;
pre-M4 rows without that status wait for a normal source refresh.

`0004_digests` adds lane/rank columns and a check constraint requiring YouTube
`final_score IS NULL`, empty breakdown/cluster, no summary, and content consisting
only of video ID plus the canonical YouTube link. Recent digest reads hydrate
current raw API counts, title, and thumbnail URLs from the existing source tables.
Titles and thumbnail URLs are not rewritten. No thumbnail or media is downloaded.
No category is displayed (in particular, never the curated YAML category).

At 30 days a digest's YouTube entries become link-only even if the source item
was recently refreshed. Purging also detaches the item's foreign-key reference;
structural lane/rank information remains, but no copied API metadata or scores.
Source raw data, snapshots, stale items, and channel caches retain their existing
30-day purge. `search.list` remains absent. The CLI is the M4 renderer; M5 must
use this same retention-aware reader, ordinary YouTube links or the official
player, unmodified thumbnails/titles, and the branding rules above.

## Alternatives considered

- Exclude YouTube: rejected by the owner because video coverage is required.
- Shared percentile/weighted score: rejected; it mixes YouTube into a common
  scale and would feed cross-source derived data.
- Persist full YouTube digest snapshots: rejected; duplicates expiry obligations
  and risks leaving API metadata in archives after its source row is purged.

## Consequences

The owner accepts residual uncertainty: the wording is open to interpretation,
particularly simple arithmetic versus the broader derived-metrics restriction.
Fallbacks are a plain chronological list of recent videos from curated channels,
or applying for an API Compliance Audit. No audit approval is claimed or sought
by this implementation. This resolved design is not another approval gate.

Lanes preserve source distinctions at the cost of a shorter digest when one
source has few candidates. YouTube archive presentation can change when current
API counts/titles refresh, then becomes link-only; it is not a historical snapshot.
No new dependency is needed: SQLAlchemy, PostgreSQL, Pydantic, and PyYAML are
already installed. A daily purge and compatible backup lifecycle remain necessary
before unattended operation.

M5 implementation note (2026-11-16): ADR 0010 uses the official logo/name link
and publishes only video ID/link from day one. The local CLI retains the recent
API-metadata display described above; exported copies need no later metadata purge.

## M6 incident addendum — 2026-11-17

Keep the seven-day lane window. Pre-change diagnosis found 70 eligible seven-day
videos from 18 channels and four already-selected videos in the owner's database.
The empty site was an unrelated two-source acceptance export, not thin uploads.
The conditional fourteen-day fallback is therefore not needed for this incident.
Legacy rows without explicit public status remain ineligible; a real API refresh
must supply that status. ADR 0012 adds shared selection/funnel predicates, source
health and export provenance checks without changing the API-only ordering or
mixing YouTube with other sources. See INCIDENT-youtube.md for exact stage counts.
