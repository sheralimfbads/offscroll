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

Owner-run live acceptance passed on 2026-11-15: two full runs collected 614 HN
stories, 57 Wikipedia topics, and 98 YouTube videos each; all final checks passed.
YouTube retained 98 item identities with 294 snapshots across three successful
runs. This illustrates identity reuse while recording new observations.

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

## M4: Select and save separate source lanes

### Data flow and module map

`build-digest` reads the latest stored observations in a UTC window. `ranking.py`
turns HN/Wikipedia metrics into source percentiles, groups similar cross-source
stories, and selects representatives under lane/publisher caps. YouTube takes a
separate SQL route in `digests.py`: recent public/embeddable videos are ordered
within that lane, with one per channel. No YouTube arithmetic result leaves SQL.

`digests.py` saves the window, config, selected items and HN/Wikipedia explanations
in one transaction. Migration `0004` adds `digests`, `digest_items`, and
`item_summaries`; earlier migrations stay unchanged. `summaries.py` supplies
source-context templates and an interface for a future chosen provider.
`retention.py` detaches old YouTube archive references. `cli.py` provides
`build-digest`, `digest`, and `explain-digest`; the old HN query is `top hackernews`.

### Worked example (synthetic)

Three HN stories have points [10, 50, 100] and comments [5, 30, 10]. The middle
story's percentiles are 0.5 and 1, so momentum is `0.6*0.5 + 0.4*1 = 0.7`.
If its title matches a Wikipedia topic, a two-source cluster gets a 1.15
multiplier. The best representative occupies its own lane; the other is linked
as additional coverage, without claiming verification.

A YouTube video has 1,000 API views and was published two days ago. SQL uses the
ratio solely to order that lane. Only its ID/link and lane position enter the
digest row. Recent reads attach current title, exact counts, and thumbnail URLs;
a digest aged 30 days displays only the video link, even if collection refreshed
that video today. Caps produce up to 6 HN + 5 Wikipedia + 4 YouTube entries and
never transfer unused slots between sources.

### Five interview questions

1. **Why separate the lanes?** Source policies and attention signals differ.
   Isolation avoids a misleading common score, at the cost of unfilled slots.
2. **Why average tied ranks?** Equal raw metrics should receive equal scores;
   deterministic identity tie-breaks make output repeatable without changing scores.
3. **Why complete-link clusters?** Every member must match every other member.
   This limits accidental chains, but can miss broad stories phrased differently.
4. **Why persist config?** It makes a saved result explainable when later weights
   change. A rebuild deliberately replaces the selected window, not the history of
   all algorithm experiments. Rolling and ISO builds have distinct identities.
5. **Why store only YouTube links in archives?** It avoids another copy of expiring
   API data. The trade-off is that recent displays change with source refreshes,
   then lose metadata rather than pretending to preserve an immutable snapshot.

### Glossary and practice

**Percentile:** relative rank inside one candidate pool. **Jaccard:** intersection
of token sets divided by their union. **Lane:** one source's independent display
section. **Complete-link:** every pair must match. **Hydration:** adding current
source fields to a stored link at read time. **Input hash:** a stable fingerprint
used to reuse the same template result. **Atomic replacement:** old or new rows
are visible together, never a half-written digest.

Try `make migrate`, `offscroll build-digest`, `offscroll digest`, and
`offscroll explain-digest` with exported settings. See [RANKING.md](RANKING.md)
for historical-window limitations and [ADR 0008](decisions/0008-m4-youtube-scoring.md)
for the accepted interpretation and fallback options. LLM integration remains
pending the owner's provider decision; templates do not claim to summarize unseen
article bodies.

### M4 P1: optional Gemini adapter

A local review hash approves exactly four public metadata fields. With an exported
key and matching approval, the digest checks the input/model/prompt cache, reserves
one of 50 UTC daily attempts in a separate transaction, and sends JSON data plus
a higher-priority system instruction to Gemini. Pydantic checks the JSON response;
errors or invalid prose become template context. Successful rows record the model,
version, tokens and zero free-tier cost. YouTube never enters this path. A rollback
cannot refund a call already made. The separate transaction makes the cap durable
but may conservatively count a process crash before HTTP as an attempt. Templates
are used for global delivery pending clearer regional permission; local CLI output
can show reviewed AI summaries. Tests use fake responses, including an instruction
injection title; no test needs an API account.

## M5: One saved digest, two delivery formats

The CLI builds a digest once; visitors only read it. `delivery.py` converts saved
lanes into an explicit public allowlist. HN/Wikipedia keep links, attention context
and deterministic template prose. YouTube keeps video IDs and links only, because
a downloaded static copy cannot reliably expire its API metadata. Local Gemini
prose also stays out of global exports. Jinja2 escapes text into a finite page;
CSS supplies mobile, light/dark and keyboard focus styles. `export-site` writes
HTML, JSON and local assets. `web/` exposes the same projection through GET routes.

Module map: delivery.py = publication boundary; templates/static = presentation;
web = read-only HTTP; backups.py = filtered SQL recovery; pipeline/pages workflows
= owner-enabled collection/publication. Make targets connect the existing pieces;
no new database migration is needed. Docker packages the optional web app under
an unprivileged UID. A static host serves files without Python or database secrets.

Worked example: a real collection yields 619 HN items and a set of Wikipedia
candidates. Ranking selects six HN and five Wikipedia items; an empty YouTube lane
stays empty. Export reads eleven saved selections, escapes a title containing `<`,
adds original/discussion links, and finishes with “That's everything for this week”.
A later page request does not recollect or spend model quota. Backing up retains
those selections but omits YouTube API rows and model prose. A restore into an empty
DB can export the digest immediately; fresh collection restores omitted metadata.

Five interview questions:
1. **Why static first?** It needs no persistent web server and exposes no DB key;
   the trade-off is rebuilding to publish changes.
2. **Why one public projection?** HTML, JSON and FastAPI share the same retention
   and model-policy boundary instead of implementing three inconsistent filters.
3. **Why filtered backups?** Full dumps would retain expiring YouTube data. Recovery
   gives up that cache and model prose in exchange for simpler retention guarantees.
4. **Why a read-only web service?** Visitor traffic cannot trigger costs, quota
   consumption or collection failures. The batch operator owns freshness.
5. **What do tests not prove?** Mocked APIs and HTML assertions do not prove current
   provider terms, source truth, hosted availability or visual accessibility.

Glossary: **ASGI** is Python's asynchronous web-server interface; **autoescape**
turns source markup into harmless text; **CSP** constrains browser resource loading;
**artifact** is a workflow-produced file bundle; **repeatable read** gives backup
data one consistent database snapshot; **restore rehearsal** tests recovery before
an incident. See RUNBOOK.md for operational commands and PROGRESS.md for evidence.

## M6: Diagnose the pipeline before changing its filters

An empty page does not tell us where data disappeared. We first counted records at
collection, storage, eligibility, saved-digest and exported-file stages. The owner
DB already held four videos; site/ came from a different test database. Fixing the
ranking window would have hidden that distinction instead of repairing delivery.

`digests.youtube_funnel` uses the same fixed predicates as selection, then reports
how many rows each step removes. `operations.source_status` adds last successful
run and freshness; safe Google error reasons survive through `PipelineError` into
run-all output. `diagnostics.doctor` checks settings presence, schema, source health,
quota, lanes and export identity without making an API call or writing database rows.
`delivery.export_site` saves digest ID/time alongside public data and detects a
concurrent rebuild. Doctor also compares HTML, so fresh JSON beside stale HTML fails.

Worked example: 104 stored videos → 73 within seven days → 71 with known status →
70 public/embeddable candidates → 18 channels → four slots. An export containing
zero videos cannot match that saved digest. Re-exporting repairs the artifact;
refreshing source data supplies missing status without inventing it. A failed
refresh is visible and does not silently deactivate configured cached channels.

Five interview questions:
1. **Why count each stage?** It separates absent data from rejected data and wrong
   output, reducing speculative fixes.
2. **Why share predicates?** A diagnostic count must describe the actual selector,
   not a subtly different copy of its rules.
3. **Why not test keys in doctor?** A read-only local check should not consume API
   quota; run-all performs authenticated collection and doctor checks its outcome.
4. **Why keep unknown errors generic?** Provider messages can contain secrets;
   fixed reason codes are useful without copying arbitrary text.
5. **Is a successful export enough?** It proves files were written, not that they
   represent the intended database. Provenance and payload comparison catch that.

Glossary: **funnel** is the sequence of candidate counts after filters;
**provenance** identifies which saved digest produced an artifact; **allowlist**
permits only known safe diagnostic fields; **Retry-After** is the server's requested
pause before another attempt. Existing transactional/idempotent storage remains;
failed API fetches retain safe run errors, not their raw error bodies.

Live acceptance also found a missing Wikipedia daily discovery list. Discovery
decides which articles to investigate; their separate 35-day histories produce the
actual metrics. We now tolerate one missing discovery day with a warning, requiring
six available lists. We still reject incomplete histories and never fill gaps with
zero. This trades some topic coverage for availability while preserving exact counts
for accepted topics (ADR 0013).
