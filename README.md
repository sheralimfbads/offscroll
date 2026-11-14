# Offscroll

A minimal Python project with a YouTube probe and PostgreSQL infrastructure for
a future weekly curated digest. The probe asks
whether YouTube's `videos.list` endpoint with `chart=mostPopular` supplies useful
candidates and the metadata needed to link to them and inspect embedding status.
It is not the digest application.

## Setup (Ubuntu/Linux)

Requires Python 3.11 or newer and its `venv` support. Run from the repository root:

```bash
python3 -m venv .venv
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
| `make install` | Install the package in editable mode with development dependencies. |
| `make lint` | Run Ruff checks on `src/`, `scripts/`, `tests/`, and `migrations/`. |
| `make format` | Format Python files in those directories with Ruff. |
| `make typecheck` | Run strict mypy checks on `src/`. |
| `make test` | Run the offline pytest suite. |
| `make check` | Run lint, type checking, and tests. |
| `make db-up` | Start PostgreSQL and wait for its healthcheck. |
| `make db-down` | Stop PostgreSQL while preserving its named volume. |
| `make migrate` | Apply Alembic migrations through the latest revision. |
| `make test-integration` | Check the migrated PostgreSQL schema. |

Ruff provides linting, import ordering, and formatting; mypy catches type errors.
Both are development-only dependencies. Stricter checks add feedback without
adding runtime dependencies; `make format` edits source files, while `make check`
does not rewrite them.
Run `make check` before submitting changes. Working rules are in [AGENTS.md](AGENTS.md),
and decision records use the [template](docs/decisions/0000-template.md).

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
also stores Alembic's revision marker. There are no collectors or ingestion jobs
yet. Future writers must sanitize error summaries before storing them.

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

## Structure and decisions

- `src/offscroll/youtube.py`: one request function, a small `Video` dataclass, and
  response validation with safe errors. Configuration is passed explicitly.
- `scripts/probe_youtube.py`: argument parsing, dotenv loading, and readable output.
- `src/offscroll/config.py` and `db.py`: environment settings and database factories.
- `migrations/`: handwritten Alembic schema changes.
- `tests/`: offline unit tests and one marked database integration test.
- `pyproject.toml`: setuptools editable installation; `httpx` and `python-dotenv`
  plus the database dependencies at runtime; pytest, Ruff, and mypy in `dev`.

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
