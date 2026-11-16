# 0005: Select Wikipedia candidates from top lists and measure complete daily series

Status: accepted
Date: 2026-11-15

## Context

M3 needs seven-day attention and a preceding 28-day baseline without scraping.
Official references checked 2026-11-15:

- [API reference](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html)
  and [getting started](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/getting-started.html)
  describe the Analytics API and its metrics endpoints.
- [Access policy](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html)
  licenses API data under CC0 and requires identifying contact information.
- [Current rate limits](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits)
  list 200 requests/minute for compliant User-Agent-only clients, subject to change.
- A public top-list request on 2026-11-15 returned HTTP 200 and 1,000 entries.

## Decision

Use seven completed UTC days ending yesterday, `en.wikipedia.org`, and `all-access`.
Filter Main_Page and known non-article namespaces; normalize Unicode to NFC and
spaces to underscores while preserving case. Sum daily top-list counts to select
60 candidates, breaking ties by title. These are candidate-selection counts only:
an article can be absent from a daily top list without having zero views.

Fetch one 35-day per-article `user` series per candidate. Its last seven days give
exact weekly views; its first 28 give mean daily baseline. Spike ratio is weekly
mean divided by baseline; a zero baseline yields null. Reject incomplete or
inconsistent series rather than inventing zero counts. Store original responses
and keep parsing pure. No descriptions, article bodies, images, or extra API are used.
For topics, `published_at` means observation-window end, explicitly marked in metadata.

Make serial requests with a one-second pause, a contact-bearing User-Agent, timeouts,
and at most three attempts for timeouts/429/5xx. Respect Retry-After; stop rather
than retry early if the requested wait exceeds 60 seconds. Retain raw responses
90 days as project policy. No new dependency is needed for this connector.

## Alternatives considered

- Treat absence from a top list as zero: biases weekly totals downward.
- Fetch 28 baseline days separately from seven current days: more requests for
  the same measurements.
- Include optional article extracts: adds text licensing and attribution work
  without helping M3's required attention metrics.

## Consequences

At most 67 requests per successful run, plus retries. Newly created articles with
incomplete history may be rejected. Yesterday's data can be delayed; a missing
top list fails the run rather than silently using a different window. Redirects
and spelling variants remain distinct API titles. Source coverage is deliberately
limited to English Wikipedia's top-list candidates; views are not factual verification.
