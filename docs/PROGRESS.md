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
- [ ] M4: Ranking, corroboration, persisted digests, and summaries.
- [ ] M5: Delivery, deployment decisions, runbook, and portfolio polish.

No historical completion tags existed at this resume check. Do not fabricate them.
The owner authorized M3 after merging M2 to main at `b9c906d`.

## Repository state and evidence

- Current branch: `m3-sources`, based on main's M2 merge `b9c906d`.
- M2 implementation commits: `2925358`, `fcff60f`, `8573c66`, `df9e49e`.
- Migrations: `0001_ingest_runs.py`, `0002_hackernews.py`; do not edit applied migrations.
- Python minor: 3.14, shared by `.python-version`, package metadata, tooling, and CI.
- Runtime dependencies are unchanged by M2.
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

## M3 work in progress

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
- Next: curated YouTube collection, durable quota reservation, retention,
  run-all/status/check-data, and tests. M3 is not complete or tagged.

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
