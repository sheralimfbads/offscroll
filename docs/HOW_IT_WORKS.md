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

## M3: More sources and operational checks (in progress)

Wikipedia starts with seven daily top lists, then measures 35 days for each of
60 candidates. This separates candidate discovery from measurement: absence from
a top list does not mean zero views. The last seven measured days become snapshot
views; the preceding 28 form the baseline. Incomplete series are rejected.
See [ADR 0005](decisions/0005-wikipedia.md). The remaining M3 walkthrough will be
completed with the YouTube, quota, retention, and data-quality slice.
