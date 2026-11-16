# Runbook

All commands run from the repository root with exported environment settings.
Never source/read `.env`. `.env.example` describes variable names only. Avoid shell
tracing, credential-bearing command arguments and raw provider/SQL error logs.

## Routine operation

1. Confirm `offscroll status`, source freshness and the target database.
2. Run `.venv/bin/offscroll purge-raw` at least daily, including during outages.
3. Run `.venv/bin/offscroll run-all` with explicitly enabled sources. Each source
   is independent; any failure or failed quality check exits nonzero.
4. Run `.venv/bin/offscroll build-digest` for rolling seven days, or `--week
   YYYY-Www` for a completed ISO week. Review `digest` and `explain-digest`.
5. Run `.venv/bin/offscroll export-site`, review `site/`, then publish only that
   directory. Never include backups, config, database dumps or environment files.

The optional six-hour collection and Monday 06:00 UTC build are commented out in
pipeline.yml. The owner must enable both the schedule and ENABLE_PIPELINE after
provisioning persistent PostgreSQL/secrets and checking retention. At Monday's
build the rolling window is used; use explicit `--week` locally for calendar-week
archives. Public deployment is a separate manual pages.yml workflow, guarded by
ENABLE_PAGES. No Gemini key is passed to either workflow.

If a source fails, collection continues for other sources. Inspect safe status and
error codes, fix the source, then rerun. Do not disable tests or invent metrics.
An HTTP 429 may require waiting; Gemini errors immediately use templates. Quotas
are durable and UTC-based; never reset counters to bypass limits. A stale digest
can remain public because exports contain no expiring YouTube API metadata.

## Local web and container

`make serve` serves localhost:8000. GET `/healthz` checks DB connectivity;
`/api/digests/latest`, `/api/digests/2026-W46` and `/` read saved data. Missing or
invalid editions return 404, unavailable DB returns a generic 503. GET does not
purge or call models. For deployed web, provision a read-only DB account and HTTPS;
static GitHub Pages does not need either a web server or DB credentials.

To run the optional app container, export APP_DATABASE_URL using the same database
credentials but host `postgres:5432`, then:

```bash
docker compose --env-file /dev/null --profile app up -d --build --wait
```

The image runs as UID 10001, with read-only root filesystem, temporary /tmp and
no Linux capabilities. Ports bind localhost. Python and Postgres base tags are
pinned; Dependabot proposes updates. `make db-down` stops without deleting data.
Do not run `down -v` against a database you intend to keep.

## Backup and tested restore

On Linux with Docker available and DATABASE_URL exported:

```bash
.venv/bin/offscroll backup --output "backups/offscroll-$(date -u +%Y%m%dT%H%M%SZ).sql"
.venv/bin/offscroll expire-backups --directory backups
```

The helper uses PostgreSQL 18.7 pg_dump for schema and a repeatable-read filtered
data snapshot. Pause migrations and concurrent backup writers. It refuses to
overwrite an existing file, writes mode 0600, and removes partial output on errors.
It omits YouTube API data and model-generated summaries, retaining video archive
ID/link and operational quotas. HN/Wikipedia raw data is restricted to 83 days;
**all copies must expire within seven days**. Do not retain older downloads.
Backups preserve source metadata and are not a private-data vault; public Actions
artifacts require particular care. See ADR 0011 for omissions and access trade-offs.

Restore only a trusted backup you created. Have the owner create a **new, empty,
disposable** PostgreSQL 18 database with an exported DATABASE_URL for that target;
never select the live database. Do not migrate the empty target before restoring.

```bash
.venv/bin/offscroll restore --input backups/offscroll-TIMESTAMP.sql
OFFSCROLL_SOURCES=hackernews,wikipedia .venv/bin/offscroll status
.venv/bin/offscroll export-site --output restored-site
.venv/bin/offscroll purge-raw
```

The command refuses nonempty targets. If restore fails, inspect the disposable
target; do not drop/retry against production. Compare digest/source counts with
the original, inspect the exported site, then recollect enabled sources. Rehearse
monthly and after schema changes. Only the owner switches production connections.
The local M5 rehearsal used disposable databases and successfully restored a real
11-item two-source digest; exact evidence is recorded in PROGRESS.md.

## Failure diagnosis and security

- Missing configuration: export settings securely; do not dump the environment.
- DB unavailable: check container health and migrations; inspect safe errors only.
- Existing volume password mismatch: recover the original credential; never erase
  a volume merely to make startup succeed.
- No digest: collect and build before export. Empty lanes are valid, no backfill.
- Wikipedia upstream failure: retry later; retain the prior digest and run purge.
- YouTube key/quota failure: inspect code-owned resource/status labels, never raw
  responses, headers or key-bearing URLs. Keep purge running even while disabled.
- Gemini template fallback: check approval hashes, daily cap and model availability;
  never enable billing to avoid a free-tier limit.
- Backup/Docker failure: confirm Linux host networking and DB connectivity. Helpers
  use PG environment variables; they do not print subprocess error payloads.

For a leaked credential, revoke/rotate it first. Owner handles history rewriting
and any force pushes after coordination; the agent never performs them. `make
secrets` scans all reachable Git blobs for documented token/credential patterns;
it cannot prove arbitrary secrets absent. Tracked dotenv files are flagged without
reading their contents. Optional pre-commit hooks run the same local checks.
