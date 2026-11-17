# 0015: Free recurring editions without an always-on database

Status: accepted; activated and verified 2026-11-17
Date: 2026-11-17 (Asia/Tashkent)

## Context and options

The owner selected Monday/Wednesday/Friday editions and wants free smartphone access
without keeping a laptop online. Existing workflows need an externally reachable
PostgreSQL server. Options: (1) GitHub Pages + a free persistent hosted database,
(2) GitHub Pages + a disposable PostgreSQL service per edition, or (3) a Worker/site
platform and a separate scheduler/data store. Choose option 2 for the first public
release: reuse the complete Python/Postgres pipeline and existing GitHub account,
without another account, billing setup or data-store rewrite. The local persistent
DB remains useful for learning, historical observations, backups and optional AI.

## Decision

New edition.yml runs at 03:17 UTC / 08:17 Asia/Tashkent Monday, Wednesday and Friday,
plus manual dispatch. It is inert unless ENABLE_EDITIONS=true and runs only on main.
The existing persistent-DB workflows stay separately disabled. Each edition uses
PostgreSQL 18 in a disposable loopback service, migrations, the full collector,
ranking, export and doctor. Only a successful checked site is uploaded/deployed;
failure leaves the last published site intact. Old editions disclose their date
and a browser stale notice. No production database credentials, Gemini key, raw API
payloads or DB backups enter the public artifact. Pages artifacts expire in one day.

A new cloud run builds from source APIs again. There is no cloud historical DB,
channel cache or summary cache; links may repeat across overlapping seven-day
windows. Cold YouTube resolution costs roughly 50–60 calls for 25 channels and the
14-day collection bound. No search.list. Deleting the runner database at job end
also removes its retained API data; published selections contain only ID/link.

### Quota accounting must survive disposable databases

The existing durable per-request database guard still applies during each run.
Additionally, cloud.py checks GitHub's workflow-run history before collection and
conservatively budgets 200 requests for every attempt, even cancelled or failed
runs. YOUTUBE_RUN_LIMIT=200 enforces that bound before requests, including retries.
A maximum 6,000 reserved calls is allowed across the current Pacific quota day,
including one hour of overlap before midnight. A job is bounded to 25 minutes and
must reach the guard within 20 minutes of creation, so the overlap covers a job
straddling midnight. Concurrent editions are serialized. Missing/malformed history,
unknown current run, API error, excess budget and reruns all fail closed. Start a
new dispatch rather than rerunning an old job. Never delete current quota-day run
history; administration can invalidate this ledger. A dedicated API project/key
is recommended: external programs or other repos are outside this guard.

### Launch boundary

After reviewing the tested candidate, the owner explicitly approved publication
and automatic editions on 2026-11-17. This supersedes the earlier never-push and
owner-only launch boundaries for M4–M7. The authorized release uses merge commits
after green CI, main as default, workflow-based Pages, the existing YouTube key
transferred in memory to its matching Actions secret, and ENABLE_EDITIONS=true.
No payment, billing change or force push. The Pages environment permits only main.
Actual remote execution and public-site evidence are recorded in PROGRESS.md.

## Residual risks and fallback

Schedules may be delayed, dropped or disabled after 60 days without repository
activity; this is not an uptime SLA. Monitor Actions failures and the edition date.
Free tiers and policies can change. Public Pages means public selections. Deleted
run history or a shared key can invalidate cross-run quota accounting: disable
editions until the next Pacific quota day or move to one persistent quota DB.
If cloud collection fails, retain the previous page and use manual dispatch after
repair. If persistent history becomes a product requirement, use a free hosted
Postgres plan after reviewing its limits; do not expose the local DB to the internet.

## Official sources verified 2026-11-17

- https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
  — public repository Pages is available on GitHub Free; size/bandwidth/build limits.
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
  — standard hosted runners in public repositories remain free; artifact storage
  has separate limits. Use standard Ubuntu and a small one-day Pages artifact.
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
  — UTC/default-branch scheduling, delays and inactivity suspension.
- https://docs.github.com/en/actions/tutorials/store-and-share-data
  — artifact retention and separation from runtime state.
- https://docs.github.com/en/rest/actions/workflow-runs#list-workflow-runs-for-a-workflow
  — created-time filtering and workflow attempt records used by the budget guard.
- https://github.com/actions/setup-node/tree/v6 — test-only Node setup and caching.

No new runtime dependency. Public hosting and actual remote execution are separate
acceptance criteria, never inferred from a local rehearsal.
