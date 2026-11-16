# 0006: Collect curated YouTube metadata with durable quota accounting

Status: accepted
Date: 2026-11-15

## Context

M3 needs a limited curated sample, not a general trending feed. Official sources
checked on 2026-11-15:

- [channels.list](https://developers.google.com/youtube/data/reference/rest/v3/channels/list)
  supports `forHandle` and `contentDetails` for the uploads playlist.
- [playlistItems.list](https://developers.google.com/youtube/data/reference/rest/v3/playlistItems/list)
  supports `playlistId` and `maxResults`; collect ten recent uploads per channel.
- [videos.list](https://developers.google.com/youtube/data/reference/rest/v3/videos/list)
  returns the requested resource parts for video IDs.
- [Quota costs](https://developers.google.com/youtube/data/determine_quota_cost)
  lists one unit for each of these methods, charges invalid requests, and resets
  daily quota at midnight Pacific Time. We do not call `search.list`.
- [Google API-key guidance](https://docs.cloud.google.com/docs/authentication/api-keys-use)
  supports the `X-Goog-Api-Key` header to avoid key-bearing URLs.

## Decision

Use an editable YAML list of 25 candidate handles covering five categories.
API resolution and collection were confirmed by owner-run acceptance on 2026-11-15;
editorial suitability and future availability still require review.
Resolve active handles through the API, cache channel ID/title/uploads playlist,
and refresh mappings at least daily when collected. Removed/disabled entries are
marked inactive. Store cache refresh time so retention can delete old entries.
The current implementation assumes one collector uses the channel config at a time.

Read the last ten uploads per channel; keep publication times within fourteen days.
Deduplicate IDs and request video metadata in batches of at most fifty. Validate
records with Pydantic; preserve missing counts as null and embeddable=false as false.
Only store returned metadata and thumbnail URLs; never download media or images.
No derived YouTube ranking metrics are implemented.

Reserve one quota unit before every attempted request in a separate committed
transaction. PostgreSQL's atomic upsert serializes competing reservations. Stop
before reaching 8,000 units; use the database's America/Los_Angeles calendar date.
Reservations survive ingestion rollback; a crash before sending may overcount one
unit, which is safer than undercounting. This extends M2's single data transaction
with independent operational accounting and cache updates. Both remain bounded.
Log units for the attempt; `quotaExceeded` fails without retrying. Store only safe
error categories and non-secret endpoint parameters. Credentials are masked settings
and sent in a header, never read from `.env` by the pipeline.

Dependencies (mainstream dependencies allowed by the brief):
- `PyYAML>=6.0.3,<7`: safe-load owner-editable channel configuration.
- `types-PyYAML>=6,<7` (development only): maintain strict typing without suppressions.
Maintainer package metadata checked 2026-11-15:
[PyYAML](https://pypi.org/project/PyYAML/), [types-PyYAML](https://pypi.org/project/types-PyYAML/).

## Alternatives considered

- Use search for discovery: unnecessary requests and broader scope.
- Put quota counters in the data transaction: failed runs would incorrectly refund
  quota; concurrent requests could exceed a check-then-update limit.
- Retain keys in URL parameters: increases accidental log and raw-endpoint exposure.
- Depend on an API SDK: more abstraction and dependencies than three GET endpoints need.

## Consequences

Curated channels and the ten-upload cap introduce editorial and sampling bias.
All collectors sharing a Google API project must use this same quota database;
the counter cannot account for external tools consuming that project's quota.
Cache refreshes can survive a later data-run failure. Failed raw/core writes remain
atomic. Local counters are conservative estimates, not the provider's authoritative
remaining quota. Live key authorization and candidate handle availability must be
checked by the owner; mocks cannot establish either.

Follow-up, 2026-11-15: owner live runs failed after 23 requests, then 12 requests
on two warm-cache attempts. A read-only database check found exactly the first
eleven configured handles cached, pointing to the twelfth entry, `@pbseons`.
Mocks reproduce both request counts when the twelfth handle does not resolve.
This localizes the likely failure but does not recover the original API response.
[PBS's published Eons address](https://www.pbs.org/video/can-you-dig-it-paleontology-and-eons-yb69ss/)
is `youtube.com/eons` (checked 2026-11-15). Change the candidate to `@eons`, with
handle/API verification still pending; a legacy channel URL alone does not prove
the current handle. No YouTube page or media was fetched for this investigation.

Preserve structured YouTube failure diagnostics in the run record and summary:
code-owned error label, resource name, one-based YAML channel position, and numeric
HTTP status when available. Never include raw exception strings, remote error
messages, URLs, headers, configuration handles, or keys. This adds actionable
context without changing retries, skipping failing channels, or weakening acceptance.

Acceptance outcome, 2026-11-15: after the `@eons` change, owner run 9 succeeded
with 98 videos and no rejections. Full runs 12 and 15 each collected the same 98
videos using 27 units; all three sources and data checks passed in both `run-all`
executions. This resolves the pending live collection check above. It does not
recover the original failed response or guarantee future handle availability.
