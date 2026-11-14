# Offscroll

A minimal Python experiment for a future weekly curated digest. This probe asks
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
python -m pytest -q
```

Tests replace HTTP calls with mocked responses and use a fake key. They do not
need `.env` or make live API calls.

## Development

Create `.venv` using the setup instructions, then run `make install`. The targets
use `.venv/bin/python` by default; override it with `make PYTHON=python check`
if you use a different environment.

| Target | Purpose |
| --- | --- |
| `make install` | Install the package in editable mode with development dependencies. |
| `make lint` | Run Ruff checks on `src/`, `scripts/`, and `tests/`. |
| `make format` | Format Python files in those directories with Ruff. |
| `make typecheck` | Run strict mypy checks on `src/`. |
| `make test` | Run the offline pytest suite. |
| `make check` | Run lint, type checking, and tests. |

Ruff provides linting, import ordering, and formatting; mypy catches type errors.
Both are development-only dependencies. Stricter checks add feedback without
adding runtime dependencies; `make format` edits source files, while `make check`
does not rewrite them.
Run `make check` before submitting changes. Working rules are in [AGENTS.md](AGENTS.md),
and decision records use the [template](docs/decisions/0000-template.md).

## Structure and decisions

- `src/offscroll/youtube.py`: one request function, a small `Video` dataclass, and
  response validation with safe errors. Configuration is passed explicitly.
- `scripts/probe_youtube.py`: argument parsing, dotenv loading, and readable output.
- `tests/`: offline tests for request parameters, output, and failure handling.
- `pyproject.toml`: setuptools editable installation; `httpx` and `python-dotenv`
  at runtime, `pytest`, Ruff, and mypy in the optional `dev` dependencies.

The `src/` layout requires installing the package rather than modifying Python's
import path. Only fields used by the probe are retained in memory. Embeddable
`false` stays `false`; missing metadata fails clearly rather than being guessed.
No web framework, database, scheduler, frontend, or AI integration is included.

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
