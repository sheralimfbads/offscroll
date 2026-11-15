# 0002: Fetch Hacker News through Algolia and retain replayable responses

Status: accepted
Date: 2026-11-15

## Context

M2 needs recent popular stories, repeatable transforms, and polite public API access.
The [official API documentation source](https://github.com/algolia/hn-search/blob/master/app/javascript/views/Api.tsx)
was checked on 2026-11-15: it documents `search_by_date`, `tags=story`, numeric
comparisons on `created_at_i` and `points`, pagination, and a 10,000 requests/hour
per-IP limit. The repository is archived; this documents the interface, not a
guarantee of future availability or unchanged limits.
The single feasibility request on 2026-11-14 returned HTTP 200 and 601 hits using
the points filter. Later collection counts can differ as the seven-day window moves.

## Decision

Use server-side date and points filters, with defensive points filtering in the
pure parser. Request 1,000 hits per page, with a configurable page cap (default
five). Reuse one client, identify Offscroll with its GitHub issues contact URL,
pause 0.5 seconds between pages, and bound timeout/429/5xx retries to three total
attempts with exponential backoff and jitter. Warn when reported hits exceed
fetched hits; do not claim completeness.

Separate network fetch from Pydantic validation. Store API responses in PostgreSQL
for replay, not article bodies or downloaded images. Reject invalid records and
count them; link accepted records to the original and HN discussion.
Retain HN raw responses for 90 days as **our project policy**, not an asserted
Algolia requirement. `purge-raw` enforces the policy when invoked.
No new dependency is needed.

## Alternatives considered

- Fetch story IDs and then individual Firebase items: more requests for this
  milestone's filtered time-window query.
- Store only normalized items: simpler storage, but no offline replay after a
  parser fix.
- Unlimited pagination and retries: greater coverage at unbounded cost and latency.

## Consequences

Fixtures can exercise parsing without network access; stored raw pages make
transform failures reproducible. Pagination can still miss items in a changing
result set, and the archived upstream repository increases maintenance uncertainty.
The 90-day purge is manual until scheduling is added. Purged runs cannot be replayed.
