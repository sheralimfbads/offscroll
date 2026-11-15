# Offscroll progress

Last resume check: 2026-11-15 (Asia/Tashkent). M3 authorized by owner `continue`.
Scope and working rules: [PROJECT_BRIEF.md](PROJECT_BRIEF.md).
The brief's embedded date is preserved verbatim; use the date above for this resume check.

## Milestone checklist

- [x] M0: YouTube feasibility probe; source and mocked tests present.
- [x] M1: PostgreSQL 18 infrastructure, migration `0001`, settings, factories, and CI present.
- [x] M2 closeout under the new brief (pipeline implementation is complete).
  - [x] Migration `0002`, HN fetch/parse connector, raw/core/snapshots, CLI and digest.
  - [x] Original local validation: 73 unit tests, 8 integration tests, working downgrade.
  - [x] Original live validation: two runs of 600 items, 1,200 snapshots, zero duplicate item keys.
  - [x] [CI succeeded for df9e49e](https://github.com/sheralimfbads/offscroll/actions/runs/43692092716).
  - [x] Save the new brief verbatim and reference it from AGENTS.md.
  - [x] Add the contact User-Agent, manual `make smoke`, API-verification ADR, and learning notes.
  - [x] Re-run local checks and integration tests for the closeout changes.
  - [x] Resolve disposable CI test credentials through the owner's delegated decision (ADR 0004).
  - [x] Commit locally and tag `m2-done`; milestone report is the stop boundary.
- [ ] M3: Wikipedia, curated-channel YouTube, quota/retention, run-all, status, and data checks.
  - [x] Migration `0003`, Wikipedia connector and complete-series validation.
  - [x] Curated YouTube connector, safe YAML config, masked/header credentials, durable quota.
  - [x] Expire raw data and individual YouTube snapshots, stale items, and channel cache.
  - [x] `run-all`, `status`, `check-data`, source enablement, and manual source smoke commands.
  - [x] Offline HTTP tests and PostgreSQL integration coverage; migration downgrade/upgrade.
  - [x] Finish two public-source live checks and record final review/commits.
  - [ ] Owner: run all three sources twice with YouTube credentials; show status/check-data.
  - [ ] Owner: push for fresh CI. Tag `m3-done` only after full live acceptance passes.
- [ ] M4: Ranking, corroboration, persisted digests, and summaries.
- [ ] M5: Delivery, deployment decisions, runbook, and portfolio polish.

At the initial M2 audit no historical completion tags existed; M2 closeout added `m2-done`.
The owner authorized M3 after merging M2 to main at `b9c906d`.

## Repository state and evidence

- Current branch: `m3-sources`, based on main's M2 merge `b9c906d`.
- M2 implementation commits: `2925358`, `fcff60f`, `8573c66`, `df9e49e`.
- Migrations: `0001_ingest_runs.py`, `0002_hackernews.py`, `0003_sources.py`;
  do not edit applied migrations.
- Python minor: 3.14, shared by `.python-version`, package metadata, tooling, and CI.
- Runtime dependencies were unchanged by M2. M3 adds PyYAML and development-only
  types-PyYAML, justified in ADR 0006.
- Original live validation used a disposable database that was removed afterward.
  Its counts are historical evidence, not a claim about the owner's current database.
- New instructions prohibit pushes. The owner pushes and merges; do not push branches or tags.

## Decisions log

- Source selection is recorded in [0001-sources.md](decisions/0001-sources.md).
- One transaction and a savepoint preserve atomic data changes while allowing ordinary
  failures to commit a safe run record. Crashes can roll back that record too.
- HN raw retention is a 90-day project policy, enforced by the manual `purge-raw` command.
- Resume M2 closeout first: its code is implemented, but the new documentation, smoke,
  contact-information, and tag requirements were not yet present.
- The new brief is authoritative over earlier workflow instructions; never push and
  stop after each milestone report.
- On 2026-11-15 the owner delegated the CI credential choice. Keep the public
  disposable test password as a narrow exception; real API/production credentials
  still require GitHub Actions secrets. This preserves fork PR testing without
  granting access to persistent data. The brief remains verbatim.
- Record the API/retention design in [ADR 0002](decisions/0002-hackernews-ingestion.md),
  transaction trade-offs in [ADR 0003](decisions/0003-run-transactions.md), and the
  Python pin, offline tests, manual smoke, and CI exception in
  [ADR 0004](decisions/0004-runtime-and-ci.md). No dependencies, applied migrations,
  CI configuration, or lint rules changed during closeout.

## Open questions / owner actions

1. **M3 live acceptance:** owner chose to run final acceptance commands locally with
   the API key exported. No key is exported to the agent; do not read `.env`.
2. **Before M4 YouTube scoring:** resolve the derived-metrics policy concern in ADR 0001.
   Hiding a computed metric from display does not by itself establish permission to compute it.
3. **Later explicit stops:** owner chooses any LLM provider, hosting, and project license.
4. Owner pushes and merges completed milestone commits/tags and runs CI for those commits.

## Current task report: M3 implemented, owner live acceptance pending

- Created `m3-sources` from merged main; no pushes.
- Added migration `0003` for source policies, YouTube channel cache (including
  refresh time for retention), and durable daily quota counters. Applied migrations
  `0001` and `0002` remain unchanged.
- Added Wikipedia fetch/parse and shared bounded HTTP handling; ADR 0005 explains
  windows, incomplete data, rate limits, and licensing.
- First slice validation: `make check` passed (92 unit tests); migrations applied
  and all 8 integration tests passed in a disposable PostgreSQL 18.7 database.
  Review risks: incomplete article histories are rejected, quota must be durable,
  and retention needs a refresh timestamp; the latter is included in `0003`.
- Added curated YouTube collection, durable quota reservation, retention,
  run-all/status/check-data, and their tests. M3 is not complete or tagged.
- Added ADRs 0006/0007, README owner acceptance instructions, and the M3 learning walkthrough.
- `make check`: Ruff passed, mypy passed for 15 source files, 114 unit tests passed.
  PostgreSQL integration: 14 passed. Verified `0003 -> 0002 -> 0003` in a fresh
  disposable database. No existing database was altered by validation.
- A final validation initially exposed a unit test assuming the default enabled
  sources despite an exported override. Fixed the test by clearing that variable
  for its default-settings assertion; no checks or lint rules were weakened.
- Public-source live validation passed twice. Each run: HN 611 fetched/upserted,
  zero rejected; Wikipedia 6,961 fetched entries, 57 topics upserted, three incomplete
  histories rejected; data checks passed. Wikipedia fetched counts include valid
  top-list candidate entries plus per-article series, not unique topic counts.
- Final SQL-backed `status`: HN 611 items / 1,222 snapshots / 2 raw responses;
  Wikipedia 57 items / 114 snapshots / 134 raw responses. Both latest runs succeeded;
  a separate `check-data` also passed. The temporary database/volume were removed.
- The owner will perform YouTube live acceptance locally. No API key was accessed,
  `.env` was never read, no push, and no completion tag yet.

Final check output:

```text
make check
All checks passed!
Success: no issues found in 15 source files
114 passed, 14 deselected in 0.44s

make test-integration
14 passed, 114 deselected in 1.27s
```

Review: checked the full intended diff, new source modules, secret-safe settings and
endpoints, quota reservation boundary, independent snapshot expiry, rollback behavior,
and owner acceptance instructions. Older migrations and CI/lint configuration are
unchanged. Unit tests still block live HTTP and DB connections; integration HTTP is
mocked. Synthetic fixtures and explicit file staging keep unrelated files out of commits.

Top three remaining risks:

1. YouTube authorization and all curated handle identities/availability remain
   unverified live; owner must complete the README's three-source acceptance before
   M3 is considered done. Editorial selection and upload caps also limit coverage.
2. Retention cannot run during extended downtime. Configure a daily purge and backup
   lifecycle before unattended YouTube collection; automatic pre-run purging alone
   does not guarantee a deadline while the application is stopped.
3. Quota accounting covers this database's collectors only. Other tools sharing the
   Google project consume quota invisibly; use the provider's console as authority.
   Channel-cache updates assume a single collector; quota increments themselves are atomic.

Next owner step: follow **Owner-run M3 live acceptance** in README (two `run-all`
commands, `status`, `check-data` with all three sources enabled). Share only safe
summaries. Owner pushes for fresh CI. Resume M3 acceptance after that evidence;
do not start M4 or create `m3-done` yet. No new owner decision is required for the
already-completed implementation.

## Previous milestone report (M2)

M2 closeout completed locally on 2026-11-15. Saved the brief verbatim, added progress
and learning docs plus three ADRs, added a contact-bearing HN User-Agent, and added
the manual smoke target with a tested Python module entry point. No M3 code was added.

Validation output:

```text
make check
All checks passed!
Success: no issues found in 9 source files
74 passed, 8 deselected in 0.59s

make db-up                     # PostgreSQL 18.7 became healthy
make migrate                   # Applied through 0002
make test-integration
8 passed, 74 deselected in 0.95s

make smoke                     # First live run
status=succeeded fetched=618 upserted=618 rejected=0
make smoke                     # Second live run
status=succeeded fetched=618 upserted=618 rejected=0

items=618
snapshots=1236
items_with_two_snapshots=618
duplicate_item_keys=0
raw_responses=2
successful_runs=2
digest_rows=15
```

Counts came from SQL queries against a fresh disposable database, including:

```sql
SELECT count(*) FROM core.items;
SELECT count(*) FROM core.item_snapshots;
SELECT count(*) FROM (
    SELECT source, external_id FROM core.items
    GROUP BY source, external_id HAVING count(*) > 1
) duplicate_item_keys;
```

Test credentials were generated in process memory; no `.env` was read. The temporary
container and volume were removed after validation. The brief matches the supplied
attachment exactly; smoke is absent from CI. Diff review found no applied migration,
dependency, CI, or lint configuration changes. The existing green CI result above
covers `df9e49e`, not these local closeout commits. The owner must push to obtain fresh CI.

Top three risks from self-review:

1. Algolia pagination is not a consistent snapshot; caps and changing results can
   omit stories. Warnings expose known truncation, but do not prove completeness.
2. Atomic runs hold a transaction during HTTP and can lose their run record on a
   process crash. Savepoints preserve ordinary failure records, not crash durability.
3. Retention currently depends on manual `purge-raw`; unattended operation needs
   scheduling. The future YouTube policy needs stricter handling than HN raw-only purging.

To try it with exported database settings: `make db-up`, `make migrate`, `make smoke`,
then `.venv/bin/offscroll digest`. CI credential choice is resolved in ADR 0004.
Local completion tag: `m2-done`. No push. Stop here and wait for owner `continue` before M3.
