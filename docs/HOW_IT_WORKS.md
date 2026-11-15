# How Offscroll works

## M2: From Hacker News responses to a digest

### Data flow

`offscroll run hackernews` opens a database transaction and records a run. One
HTTP client fetches recent stories from Algolia. Raw JSON pages land in
`raw.api_responses`; a pure parser validates each hit with Pydantic. Valid records
become stable identities in `core.items` and observations in `core.item_snapshots`.
The latest-metrics view joins each item to its newest observation. `offscroll digest`
selects up to 15 HN stories published in the last seven days, ordered by score.
This ranks attention; it does not establish truth.

### Module map

| File | Responsibility |
| --- | --- |
| `cli.py` | Parse commands, configure logging, print safe results/errors. |
| `config.py`, `db.py` | Validate exported settings and create database connections. |
| `connectors/_base.py` | Define the small fetch/parse contract and shared records. |
| `connectors/hackernews.py` | Fetch bounded pages; validate and normalize hits. |
| `pipeline.py` | Land raw data, upsert items, save snapshots, query digest, purge. |
| `migrations/versions/0002_hackernews.py` | Define tables, constraints, and latest view. |
| `tests/` | Offline parsing/HTTP tests and transactional PostgreSQL tests. |

### Worked example (synthetic, not a live result)

Suppose story `123` has 70 points and URL `https://www.example.com/story`.
Run 10 stores its raw page, validates the hit, normalizes the domain to
`example.com`, and creates one item plus snapshot `(item_id, 10)`. Its discussion
link is `https://news.ycombinator.com/item?id=123`. A malformed neighbor increases
the rejected counter without blocking the valid story.

Run 11 sees the same story with 90 points. The item's identity stays the same;
snapshot `(item_id, 11)` records the new count. Replaying run 10 neither adds a
third snapshot nor overwrites newer item metadata. The digest reads 90 points.
After 90 days, `purge-raw` can remove the old response while preserving items,
snapshots, and run history; replay of that deleted response is then impossible.

### Five interview questions

1. **Why separate fetch and parse?** Network code has retries and failures; a pure
   parser produces the same output for the same payload and is easy to test offline.
2. **Why keep raw data?** It supports inspection and replay after parser fixes,
   at the cost of storage and a retention obligation.
3. **What makes runs idempotent?** Unique item keys and snapshot conflict handling.
   Replaying one run adds nothing; distinct runs intentionally add observations.
4. **Why use a savepoint?** It rolls back data writes while allowing the outer
   transaction to retain an ordinary failure log. A process crash can still erase
   the whole transaction, and `running` is not externally visible in flight.
5. **Why separate integration and smoke tests?** Integration tests exercise real
   PostgreSQL with mocked HTTP. Manual smoke checks use the changing live service;
   keeping them out of CI avoids flaky builds and credential requirements.

### Glossary and practice

**Upsert:** insert or update a row with the same identity. **Snapshot:** metrics
observed at a particular time. **Transaction:** changes committed or rolled back
together. **Savepoint:** a rollback boundary inside a transaction. **Migration:**
a versioned schema change. **Retention:** how long stored data may remain.
**Backoff:** increasing delay before a retry. **ADR:** a recorded design decision.

After exporting database settings, try `make migrate`, `make smoke`, and
`.venv/bin/offscroll digest`. Run `make check` and `make test-integration` for
repeatable checks. Smoke writes real data; use a disposable database for experiments.
See ADRs [0002](decisions/0002-hackernews-ingestion.md),
[0003](decisions/0003-run-transactions.md), and [0004](decisions/0004-runtime-and-ci.md)
for the limits and alternatives behind these choices.

## M3: More sources, quota, retention, and quality

Implementation walkthrough; final three-source live acceptance remains owner-run.

### Data flow

Wikipedia starts with seven completed daily top lists, filters non-article pages,
and selects 60 candidates. Each gets a 35-day per-article series: seven recent days
for views, 28 preceding days for the mean baseline. Missing top-list entries are
not zero views; incomplete measured series are rejected.

YouTube starts with the owner's YAML handles. The API resolves channel IDs and
uploads playlists, then supplies ten uploads per channel. Recent video IDs are
deduplicated and fetched in groups of fifty. API-provided metrics become snapshots;
we do not compute YouTube ranking metrics. Each attempted request first commits a
quota reservation. Raw/core data still commits atomically for each source run.

`run-all` attempts enabled sources independently, prints their outcomes, and runs
quality checks. `status` exposes last attempts, snapshot times, counts, and quota.
The purge job removes expired raw data plus YouTube snapshots, stale items, and
old channel-cache entries.

### Module map

| File | Responsibility |
| --- | --- |
| `connectors/wikipedia.py` | Candidate selection, daily series validation and metrics. |
| `connectors/youtube.py` | Safe YAML loading, handle cache, uploads and video metadata. |
| `connectors/_http.py` | Safe errors, bounded retries, contact User-Agent, Retry-After. |
| `quota.py` | Atomic quota reservations using the Pacific calendar day. |
| `retention.py` | Delete expired raw/core data without network requests. |
| `operations.py` | Run sources independently and inspect database quality. |
| `config.py`, `cli.py` | Exported settings, masked keys, operational commands. |
| `0003_sources.py` | Versioned channel cache, quota table, and source policies. |

### Worked example (synthetic)

A Wikipedia candidate has 100 views/day over its preceding 28 days and 200/day
over its recent seven days. It gets snapshot views=1,400, baseline=100, and
spike_ratio=2. Its topic date means observation-window end, not article creation.

A YouTube channel has one recent video. A cold cache needs three requests:
channel, uploads, video. Three units are reserved. The next run reuses the channel
cache and needs two. The item identity stays stable and a second snapshot is added.
After thirty days, the first snapshot expires even if the item was refreshed today.
If Wikipedia fails, HN and YouTube still run, but `run-all` exits nonzero.

### Five interview questions

1. **Why commit quota separately?** Failed ingestion still consumed requests.
   Rolling back quota would undercount; a pre-request crash can conservatively overcount.
2. **How does concurrency affect quota?** PostgreSQL locks the conflicting daily row
   during its atomic increment. A separate read-then-write check could race.
3. **Why expire snapshots individually?** Refreshing today's metadata does not
   refresh last month's observed metrics. Their retention clocks are independent.
4. **What does freshness mean?** Snapshot capture time must be within 36 hours.
   It measures collection health, not whether a claim is current or true. Wikipedia
   also records its actual measurement window in metadata.
5. **Why retain YAML and a database cache?** YAML is the owner's editorial input;
   the cache contains resolved, expiring API metadata. This saves requests while
   keeping configuration editable, at the cost of refresh and purge rules.

### Glossary and practice

**Baseline:** prior-period typical activity. **Quota reservation:** durable accounting
before an API request. **Atomic increment:** a database update other workers cannot
interleave incorrectly. **Cache:** reusable fetched metadata with an expiry.
**Freshness:** elapsed time since observation. **Failure isolation:** one source's
failure does not suppress attempts for the others.

Try `offscroll status`, `offscroll check-data`, and `offscroll purge-raw` after
collection. Use the README's acceptance commands locally; never share keys.
Read ADRs [0005](decisions/0005-wikipedia.md), [0006](decisions/0006-youtube-collection.md),
and [0007](decisions/0007-retention-and-quality.md). Schedule purging before unattended
use: an application that is stopped cannot enforce deletion deadlines itself.

When a run fails, inspect its safe code, `resource`, and `channel_index` in the
summary or `status`. The index counts entries in YAML from one, including disabled
entries. For example, an unresolved twelfth handle plus eleven cached playlists
uses twelve requests. Counts can localize a fault; they cannot prove its cause.
