# Offscroll

A small Python metadata pipeline collecting Hacker News, Wikipedia pageviews, and
curated YouTube metadata into PostgreSQL, with a simple Hacker News digest.
Cross-source ranking and delivery come in later milestones. The separate YouTube probe asks
whether YouTube's `videos.list` endpoint with `chart=mostPopular` supplies useful
candidates and the metadata needed to link to them and inspect embedding status.
It remains a standalone feasibility experiment.

## Setup (Ubuntu/Linux)

Use Python **3.14**, pinned in `.python-version`, with its `venv` support. CI reads
the same file, and `make install` / `make check` reject a different minor version.
Run from the repository root:

```bash
make venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

If `venv` is unavailable on Ubuntu, install it with
`sudo apt install python3-venv` (or the package matching your Python version).

In your Google Cloud project, enable **YouTube Data API v3** and create an API key;
see Google's [setup guide](https://developers.google.com/youtube/v3/getting-started).
Edit `.env` locally to fill in `YOUTUBE_API_KEY`. Never commit or share that file.
An existing `YOUTUBE_API_KEY` environment variable takes precedence over `.env`.
The probe reads `.env` from the repository root, independent of your working directory.

## Run

```bash
python scripts/probe_youtube.py
python scripts/probe_youtube.py --region-code GB --max-results 5
python scripts/probe_youtube.py --help
```

Defaults: region `US`, maximum `10` results; the allowed range is `1–50`.
Each run makes one GET request with `part=snippet,status` and `chart=mostPopular`.
It prints video ID, title, channel name, publish time as returned by the API,
watch URL, and embeddable status. An empty result gets an explicit message.
Failures print a concise error to stderr and exit with status 1; argparse uses
status 2 for command-line syntax errors.

There is a 10-second HTTP timeout, no automatic retry, and no pagination. Errors
cover missing keys, connectivity, timeouts, malformed responses, unavailable
charts, denied access, and quota/rate limits. Diagnostics omit raw API bodies,
request URLs, and keys. There is no media downloading, scraping, or data storage.

## Tests

```bash
make test
```

Unit tests mock HTTP calls and block database connections. They do not need `.env`,
PostgreSQL, or live API calls. The separate integration test requires a migrated
database and skips when `DATABASE_URL` is unset.

## Development

Create `.venv` using the setup instructions, then run `make install`. The targets
use `.venv/bin/python` by default; override it with `make PYTHON=python check`
if you use a different environment.

| Target | Purpose |
| --- | --- |
| `make venv` | Create `.venv` with the Python minor from `.python-version`. |
| `make check-python` | Verify that the active project interpreter matches the pin. |
| `make install` | Install the package in editable mode with development dependencies. |
| `make lint` | Run Ruff checks on `src/`, `scripts/`, `tests/`, and `migrations/`. |
| `make format` | Format Python files in those directories with Ruff. |
| `make typecheck` | Run strict mypy checks on `src/`. |
| `make test` | Run the offline pytest suite. |
| `make check` | Run lint, type checking, and tests. |
| `make db-up` | Start PostgreSQL and wait for its healthcheck. |
| `make db-down` | Stop PostgreSQL while preserving its named volume. |
| `make migrate` | Apply Alembic migrations through the latest revision. |
| `make test-integration` | Check migrations and pipeline behavior against PostgreSQL. |
| `make smoke` | Manual live HN check; use `SMOKE_SOURCE=wikipedia` or `youtube` for M3. |

Ruff provides linting, import ordering, and formatting; mypy catches type errors.
Both are development-only dependencies. Stricter checks add feedback without
adding runtime dependencies; `make format` edits source files, while `make check`
does not rewrite them.
Run `make check` before submitting changes. Working rules are in [AGENTS.md](AGENTS.md),
and decision records use the [template](docs/decisions/0000-template.md).

The [project brief](docs/PROJECT_BRIEF.md) defines scope; [PROGRESS.md](docs/PROGRESS.md)
records milestone status and open questions. Read [HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)
for the learning walkthrough. The owner pushes and merges; automation stops after
each milestone report until the owner says `continue`.

## Local PostgreSQL

Install Docker Engine and the Docker Compose plugin, then run `make install` to
install the database dependencies. The image is pinned to `postgres:18.7-bookworm`.
It binds port 5432 to `127.0.0.1` and stores data in a named volume mounted at
`/var/lib/postgresql`, as required by the PostgreSQL 18+ image layout. `PGDATA` is
not overridden. See the [official image documentation](https://hub.docker.com/_/postgres).

Database settings and Make targets use **exported environment variables only**.
They do not load `.env`; Compose explicitly uses `--env-file /dev/null`.
`.env.example` documents the required names with placeholders. Set the values
locally; these Bash prompts keep the password and URL out of shell history:

```bash
export POSTGRES_USER=offscroll
export POSTGRES_DB=offscroll
read -rsp 'PostgreSQL password: ' POSTGRES_PASSWORD
printf '\n'
export POSTGRES_PASSWORD
read -rsp 'Database URL: ' DATABASE_URL
printf '\n'
export DATABASE_URL

make db-up
make migrate
make test-integration
make db-down
```

The URL format is `postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/DATABASE`.
Its credentials and database must match the `POSTGRES_*` variables. Percent-encode
special characters in URL credentials. If host port 5432 is occupied, export
`POSTGRES_PORT=55432` and use that port in `DATABASE_URL`. Query parameters are
currently rejected so credentials cannot leak through SQLAlchemy's unmasked URL
query representation.
Do not print settings, connection errors, or resolved Compose configuration when
diagnosing credentials; the provided settings mask secrets and migration errors
use fixed messages.

The first migration, `0001`, creates `raw`, `core`, and `marts`, plus
`raw.ingest_runs`: an identity primary key, source, timezone-aware start/finish
timestamps, status, fetched item count, and optional error summary. The database
also stores Alembic's revision marker. Migration `0002` adds raw API responses,
sources, items, snapshots, the latest-metrics view, and a rejected-item counter.
Pipeline failures store fixed error categories, never raw exception messages.

`make migrate` is safe to repeat after a successful upgrade. Downgrading `0001`
would delete the run log and remove the schemas; it refuses to cascade through
unrelated objects. `make db-down` preserves data. PostgreSQL's initialization
variables only set credentials on the first start with an empty volume; changing
them later does not update an existing database password.

Pydantic-settings validates environment configuration; SQLAlchemy provides engine
and session factories; psycopg 3 connects to PostgreSQL; Alembic versions the
schema. Factories do not connect at import time. Engines hide SQL parameters and
disable SQL echo. Keeping synchronous factories and handwritten migrations makes
this foundation easier to explain, while advanced connection options and model
autogeneration remain future work.

On pushes and pull requests, [CI](.github/workflows/ci.yml) runs `make check`,
then applies migrations and runs the integration test against a disposable
PostgreSQL service. Its public placeholder credentials require no CI secrets.
This disposable test fixture is the narrow exception documented in
[ADR 0004](docs/decisions/0004-runtime-and-ci.md); real API and production credentials
must use GitHub Actions secrets.

## Hacker News pipeline

Activate `.venv`, export the database settings as above, and run:

```bash
make db-up
make migrate
offscroll run hackernews
offscroll digest

# Fetch without transforming; then replay stored responses without network calls.
offscroll ingest hackernews --min-points 20 --page-cap 5
offscroll transform                 # latest run that still has raw responses
offscroll transform --run-id 123     # replace 123 with a logged run_id
offscroll purge-raw
```

For a bounded manual live check, run `make smoke` after migrating the database.
It writes a real run and at most one page of API data; a truncation warning means
more results exist beyond that cap. It never runs in CI. Tests remain offline
for HTTP, including the PostgreSQL integration suite.

```mermaid
flowchart LR
    HN[HN Algolia API] -->|fetch| Raw[raw.api_responses]
    Raw -->|pure parse and validation| Items[core.items]
    Raw -->|metrics per item and run| Snapshots[core.item_snapshots]
    Items --> Latest[marts.latest_item_metrics]
    Snapshots --> Latest
    Latest --> Digest[Top 15 stories from the last 7 days]
    Runs[raw.ingest_runs] -. run status and counts .-> Raw
    Retention[core.sources retention policy] -->|purge-raw| Raw
```

The connector calls Algolia's `search_by_date` with `tags=story`, a seven-day
`created_at_i` cutoff, `points>=20` by default, and `hitsPerPage=1000`. A single
live feasibility request on 2026-11-14 confirmed that the points filter works;
parsing also enforces the threshold defensively. `--min-points` changes that
threshold. `--page-cap` defaults to five. The connector warns when `nbHits` exceeds
the fetched hit count; a capped or shifting result set is not claimed to be complete.

Each fetch uses one HTTP client, an identifying User-Agent, a 15-second timeout
(five seconds for connecting), and a 0.5-second pause between pages. Only timeouts,
429, and 5xx responses are retried: at most three total attempts per page, with
exponential delays and jitter. Other failures stop the run. HTTP response bodies,
request URLs, and exception details are not logged.

Pydantic validates each hit. Invalid hits increase `items_rejected`; valid hits
below the requested points threshold are filtered out, not rejected. `items_fetched`
counts all returned hits. The summary's `upserted` count is the number of distinct
accepted items processed, including existing items. Raw endpoint values contain
only the fixed API path and non-secret filter/pagination parameters. Raw JSON is
stored in PostgreSQL, not printed by the CLI.

`run` lands raw responses and transforms them in one transaction. A savepoint
rolls back data changes on failure while the outer transaction commits the failed
run record. `running` is therefore not externally visible before completion;
a process crash or lost database connection can roll back the whole transaction,
including that run record. Each completed attempt emits one `key=value` summary
with fetched, upserted, rejected, and duration fields.

`ingest` commits raw data only. `transform` reuses the selected run ID and original
fetch timestamps; replay cannot add duplicate `(item_id, run_id)` snapshots or
overwrite newer item metadata. A new `run` reuses item identities and adds fresh
snapshots. First-seen timestamps are preserved. Core tables use explicit bound
SQL through SQLAlchemy Core; no ORM models are used by the pipeline.

The digest selects the latest snapshot per item (ties break by run ID), filters
HN stories by publish time within the last seven days, and orders by score
descending with stable tie-breakers. It prints up to 15 rows with rank, score,
comments, title, URL, discussion URL, and domain. This is an attention ranking,
not factual verification, summarization, or cross-source corroboration.

**Retention:** Offscroll's own policy retains HN raw API responses for 90 days,
recorded in `core.sources`. `purge-raw` deletes expired raw responses according to
that table and preserves core items, snapshots, and run logs. It is a manual
command in this milestone; schedule it before unattended collection. Purged runs
can no longer be replayed. Links point to originals; article pages are not scraped.

To add a source, add one module under `src/offscroll/connectors/` exporting a
`connector` (or `create_connector(engine)` for database-backed setup) that implements the small Protocol in `_base.py`, including its
retention rule. `fetch` performs I/O and returns raw pages; `parse` is a pure
payload-to-records function. The module loader and common transform need no new
registry entry. HN-specific digest selection remains deliberate for this milestone.

Unit tests use two synthetic JSON fixtures and `httpx.MockTransport`; live HTTP
is blocked in all tests. Database integration tests cover two runs, replay,
rejection counts, savepoint rollback, ordering, and purging. Run them against a
dedicated test database: pipeline test writes and temporary cleanup are wrapped
in an outer transaction that is rolled back, but can hold locks while running.

## M3: Wikipedia, curated YouTube, and operational checks

Run from the repository root after `make install` and exporting database settings.
The pipeline uses exported environment variables only; it never loads `.env`.
Migration `0003` adds the source policies, channel cache, and daily quota counters.

```bash
make db-up
make migrate

# Public sources can be exercised without YouTube credentials.
export OFFSCROLL_SOURCES=hackernews,wikipedia
.venv/bin/offscroll run-all
.venv/bin/offscroll status
.venv/bin/offscroll check-data

# Single-source manual checks (live HTTP and database writes).
make smoke SMOKE_SOURCE=wikipedia
.venv/bin/offscroll run youtube

# Network-free retention job, including expired YouTube core data.
.venv/bin/offscroll purge-raw
```

`OFFSCROLL_SOURCES` defaults to `hackernews,wikipedia,youtube`. Every enabled source
is attempted independently by `run-all`; one failed source does not skip the rest.
It prints a summary table and always runs `check-data` afterward, exiting nonzero
on either collection or quality failure. `status` reports last attempt, latest
snapshot time (`data_at`), item/snapshot/raw counts, and quota usage. Checks require
fresh data within 36 hours, nonempty items with snapshots, valid required fields,
unique identities, sensible metrics, and no expired YouTube data. An empty source
is treated as a problem to investigate, not silently declared healthy.

Wikipedia selects up to 60 candidates from seven completed UTC daily top lists,
excluding Main_Page and known non-article namespaces. It fetches 35 daily per-article
counts for each candidate: the last seven give weekly views, the preceding 28 give
the mean baseline. Incomplete series are rejected; a zero baseline gives a null
spike ratio. `published_at` for topics is explicitly the observation-window end,
not the article's creation date. API data is CC0; no article descriptions or images
are collected. One-second spacing keeps requests serial and below current limits.
See [ADR 0005](docs/decisions/0005-wikipedia.md).

YouTube uses [config/youtube_channels.yaml](config/youtube_channels.yaml), or the
path in `YOUTUBE_CHANNELS_FILE`. These 25 handles are an editable editorial starting
list. Owner-run live collection passed on 2026-11-15; review channel choices as they
change. Resolve handles via
`channels.list`, cache uploads playlists with a daily refresh, fetch ten uploads per
active channel, keep the last fourteen days, and query `videos.list` in batches of
fifty. No search, scraping, media downloads, or derived ranking metrics are used.
Thumbnail URLs are stored as returned, never downloaded. Missing metrics stay null.
PyYAML safely loads configuration; its development stubs preserve strict typing.

The key travels in `X-Goog-Api-Key`, not a URL. A separate atomic transaction reserves
one unit before every HTTP attempt, including retries. The local guard stops before
8,000 units per Pacific calendar day, survives failed runs, and logs attempted units.
All collectors for the same API project must share this quota database; external
tools' usage is not visible here. `quotaExceeded` is never retried. Run one collector
at a time for predictable channel-cache updates. See [ADR 0006](docs/decisions/0006-youtube-collection.md).

**Retention:** HN/Wikipedia raw responses expire after 90 days. YouTube raw responses,
individual snapshots, stale item metadata, and cached channels expire within 30 days.
A fresh item does not extend old snapshots' lifetime. Purging runs independently
before `run-all`, YouTube collection, and replay, and through `purge-raw`.
For unattended use, schedule the purge at least daily and apply matching backup
retention; no external scheduler or backup lifecycle is configured yet. A stopped
application cannot purge itself. See [ADR 0007](docs/decisions/0007-retention-and-quality.md).

### Owner-run M3 live acceptance

Use a dedicated local database. After exporting its settings and enabling YouTube
Data API v3 for your key, enter the key locally without putting it in shell history:

```bash
read -rsp 'YouTube API key: ' YOUTUBE_API_KEY
printf '\n'
export YOUTUBE_API_KEY
export OFFSCROLL_SOURCES=hackernews,wikipedia,youtube
make install
make db-up
make migrate
make check
make test-integration
.venv/bin/offscroll run-all
.venv/bin/offscroll run-all
.venv/bin/offscroll status
.venv/bin/offscroll check-data
unset YOUTUBE_API_KEY
```

Expect three successful sources on each run, nonzero item counts, and `check=passed`.
Snapshots should grow while item identities are reused; new live stories can make
item counts grow too. Share only command summaries, never keys or connection URLs.
The owner completed this acceptance on 2026-11-15: both full runs succeeded for all
three sources, each upserting 614 HN stories, 57 Wikipedia topics, and 98 YouTube
videos. The final data checks passed. See [PROGRESS.md](docs/PROGRESS.md) for run IDs,
accumulated counts, and remaining operational risks. Mocks alone cannot establish
live authorization, and future data/counts can change.

For a YouTube failure, retry only `.venv/bin/offscroll run youtube` after addressing
the reported issue. Diagnostics include a safe error code, API resource name,
`channel_index` (one-based position in the YAML list, including inactive entries),
and HTTP status when available. For example, `youtube_handle_unresolved
resource=channels channel_index=12` identifies the entry to inspect without dumping
the API response. `status` retains that diagnostic after rollback. Historical
`source_error` records cannot recover details that were not stored. Once YouTube
succeeds, repeat the full two-run acceptance above.

## Structure and decisions

- `src/offscroll/youtube.py`: one request function, a small `Video` dataclass, and
  response validation with safe errors. Configuration is passed explicitly.
- `scripts/probe_youtube.py`: argument parsing, dotenv loading, and readable output.
- `src/offscroll/config.py` and `db.py`: environment settings and database factories.
- `src/offscroll/connectors/`: network fetchers and pure payload parsers.
- `src/offscroll/pipeline.py` and `cli.py`: transactional SQL and argparse commands.
- `migrations/`: handwritten Alembic schema changes.
- `tests/`: offline unit tests and marked database integration tests.
- `pyproject.toml`: setuptools editable installation; `httpx` and `python-dotenv`
  plus database dependencies and PyYAML at runtime; pytest, Ruff, mypy, and YAML
  typing stubs in `dev`.

The `src/` layout requires installing the package rather than modifying Python's
import path. Only fields used by the probe are retained in memory. Embeddable
`false` stays `false`; missing metadata fails clearly rather than being guessed.
PostgreSQL infrastructure is included; web framework, scheduler, frontend, and AI
integrations remain outside the current milestone.

## What this experiment can establish

Run the probe manually with your key to assess candidate relevance, chart
availability for your region, metadata completeness, and embedding flags.
The mocked tests cannot verify live authorization, quota, regional availability,
actual returned videos, or real playback/embedding behavior.

YouTube's `mostPopular` chart now includes trending Music, Movies, and Gaming
videos, following the July 2025 change. It is not a broad sample of all topics
or a list restricted to the last week. A single successful request cannot
establish suitability for a weekly digest; repeated manual observations would
help assess relevance and repetition. See the official
[chart guide](https://developers.google.com/youtube/data/guides/implementation/videos?hl=en)
and [revision history](https://developers.google.com/youtube/v3/revision_history).
The `embeddable` flag alone does not verify playback in a future application.

Request parameters and `videoChartNotFound` follow the
[videos.list reference](https://developers.google.com/youtube/data/reference/rest/v3/videos/list?hl=en);
quota handling follows the
[API error reference](https://developers.google.com/youtube/data/reference/rest/v3/errors?hl=en).

## Build a digest (M4)

With database settings already exported (the application does not read `.env`):

```bash
make migrate
.venv/bin/offscroll build-digest
.venv/bin/offscroll digest
.venv/bin/offscroll explain-digest
# An explicit ISO week; rebuild replaces the saved week:
.venv/bin/offscroll build-digest --week 2026-W46
.venv/bin/offscroll digest --week 2026-W46
# The original M2 single-source query:
.venv/bin/offscroll top hackernews
```

Collect sources first with `offscroll run-all` when fresh data is needed.
Pre-M4 YouTube rows require a normal collection refresh before eligibility because
M4 requires explicit public status. Building itself uses the database only.
The digest has separate HN (max 6), Wikipedia (max 5), and YouTube (max 4) lanes;
short lanes are not backfilled. YouTube has one video per channel, no common
score, no cross-source clustering, and no saved or displayed derived metric.
Archived YouTube entries become link-only at 30 days. Schedule `purge-raw` daily
before unattended use; include backups in retention planning.

Templates are labelled source context, not AI summaries. LLM provider selection
is pending. See [ranking formulas and limitations](docs/RANKING.md) and
[the accepted YouTube lane decision](docs/decisions/0008-m4-youtube-scoring.md).
M4 provides a CLI display; the HTML site and graphical branding are M5 work.
