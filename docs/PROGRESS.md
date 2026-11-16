# Offscroll progress

Last resume check: 2026-11-16 (Asia/Tashkent). M3 is complete locally; M4 preflight
identified a requirements conflict requiring an owner decision (ADR 0008).
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
- [x] M3: Wikipedia, curated-channel YouTube, quota/retention, run-all, status, and data checks.
  - [x] Migration `0003`, Wikipedia connector and complete-series validation.
  - [x] Curated YouTube connector, safe YAML config, masked/header credentials, durable quota.
  - [x] Expire raw data and individual YouTube snapshots, stale items, and channel cache.
  - [x] `run-all`, `status`, `check-data`, source enablement, and manual source smoke commands.
  - [x] Offline HTTP tests and PostgreSQL integration coverage; migration downgrade/upgrade.
  - [x] Finish two public-source live checks and record final review/commits.
  - [x] Owner: run all three sources twice with YouTube credentials; show status/check-data.
  - [x] Record acceptance, rerun local checks, commit closeout, and tag `m3-done`.
  - [ ] Owner: push branch/tag for fresh CI and merge; automation never pushes.
- [ ] M4: Ranking, corroboration, persisted digests, and summaries.
- [ ] M5: Delivery, deployment decisions, runbook, and portfolio polish.

At the initial M2 audit no historical completion tags existed; M2 closeout added `m2-done`.
The owner authorized M3 after merging M2 to main at `b9c906d`.

## Repository state and evidence

- Current branch: `m4-ranking`, starting at M3 closeout `de119e2` (`m3-done`).
- Resume began with a clean working tree on `m3-sources`. Local `main` and the
  cached `origin/main` reference still point to `b9c906d`; no remote fetch was
  performed, so this does not establish the current remote merge state.
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

1. **M3 acceptance passed:** owner supplied successful live results for runs 10–15.
   No API key was shared with the agent. Owner pushes the completed branch/tag for fresh CI.
2. **Before M4 implementation:** choose the concrete proposal in
   [ADR 0008](decisions/0008-m4-youtube-scoring.md): defer YouTube from the M4
   digest, or establish applicable permission for the original design.
   Official policies were rechecked on 2026-11-16; hiding a computed metric
   does not establish permission to compute it.
3. **Later explicit stops:** owner chooses any LLM provider, hosting, and project license.
4. Owner pushes and merges completed milestone commits/tags and runs CI for those commits.

## M4 resume preflight: owner decision pending

The owner's continuation request advances work to M4. Before implementation,
the recorded YouTube policy issue was checked against official sources and
documented as a proposed decision in ADR 0008. The recommendation retains M3
collection but limits M4 ranking and clustering to HN/Wikipedia, producing at
most 12 selected items with the existing source caps. This changes scope and
requires an explicit owner decision under brief section 8.

This preflight changes documentation only. No new dependencies, runtime behavior,
schema, applied migrations, CI settings, or lint rules changed. M4 implementation
and its acceptance tests remain outstanding; there is no M4 completion tag.

Validation: `make check` passed Ruff, strict mypy (15 source files), and 118 unit
tests (15 integration tests deselected). `make migrate` and
`make test-integration` passed against disposable PostgreSQL 18.7: 15 integration
tests passed, 118 deselected. The container and temporary storage were removed.
No `.env` or existing credentials were read; the owner's database was untouched.

Self-review: the proposal is explicitly pending, the project brief is preserved,
and local branch state is distinguished from unqueried remote state.
Top three risks:

1. Excluding YouTube reduces coverage and caps the digest at 12 items; clustering
   and domain limits can reduce it further.
2. YouTube permission and applicability remain unestablished; the owner cannot
   resolve that by merely approving a hidden derived score.
3. M3 push/merge and fresh CI remain unconfirmed; this M4 branch includes M3's
   local commits and may need reconciliation after the owner's merge.

## Previous milestone report: M3 complete locally

Owner-provided live output on 2026-11-15 establishes two successful `run-all`
executions, successful `status` for all three sources, and a final `check-data` pass.
These are owner-run results, not additional live requests made by the agent.

| Source | First run | Second run | Fetched per run | Upserted per run | Rejected per run |
| --- | ---: | ---: | ---: | ---: | ---: |
| Hacker News | 10 | 13 | 614 | 614 | 0 |
| Wikipedia | 11 | 14 | 6,961 | 57 | 3 |
| YouTube | 12 | 15 | 98 | 98 | 0 |

All six runs succeeded. Both `run-all` calls ended with `check=passed`; the separate
`check-data` command also passed. Wikipedia's fetched count includes discovery-list
entries; the three incomplete daily series were rejected rather than filled with
invented counts. Each YouTube run reserved 27 units using the channel cache.

Final owner-provided `status` (cumulative database history, not just these two runs):

| Source | Items | Snapshots | Raw responses | Daily quota units |
| --- | ---: | ---: | ---: | ---: |
| Hacker News | 634 | 3,076 | 5 | 0 |
| Wikipedia | 57 | 228 | 268 | 0 |
| YouTube | 98 | 294 | 95 | 142 |

YouTube's 294 snapshots equal 98 videos across standalone successful run 9 and
acceptance runs 12/15. Its daily total includes earlier failed requests as intended.
No reset of the owner's database or quota counters was necessary.

### Implementation and debugging evidence

- Branch `m3-sources` starts at main's M2 merge `b9c906d`; implementation commits
  are `7bd1e54`, `b78b129`, and `72032f5`.
- Migration `0003` adds source policies, channel cache with retention timestamp,
  and durable quota counters. Earlier migrations are unchanged. Its downgrade to
  `0002` and upgrade back to `0003` passed in a disposable database.
- Wikipedia selects candidates from seven completed daily top lists, then measures
  complete 35-day series. YouTube resolves curated handles, reuses uploads playlists,
  batches video requests, and reserves quota before each attempt.
- `run-all`, `status`, `check-data`, source enablement, safe diagnostics, and independent
  raw/core retention are implemented. ADRs 0005–0007 record their trade-offs.
- Earlier owner YouTube attempts failed after 23, 12, and 12 units. A read-only cache
  inspection found the first eleven configured handles, implicating the twelfth,
  `@pbseons`. Mocks reproduce that pattern. The original discarded response cannot
  prove its exact reason. Changing the candidate to `@eons` was followed by successful
  live collection (run 9: 98 videos, 41 units), then the full acceptance above.
- Diagnostics now retain code-owned error labels, resource, YAML position, and numeric
  HTTP status through rollback. Remote messages, URLs, headers, and secrets stay out.
- Prior agent live checks independently passed twice for public HN/Wikipedia only,
  ending with 611 HN items/1,222 snapshots and 57 Wikipedia topics/114 snapshots in
  a disposable database. Those historical counts are separate from the owner's data.

### Closeout checks and review

`make check`: Ruff passed; strict mypy passed for 15 source files;
118 unit tests passed, 15 integration tests deselected (0.47s).
`make test-integration`: 15 passed, 118 deselected (1.43s).
The database check used a separate disposable container/volume and mocked HTTP;
both were cleaned up afterward. No `.env` or API key was read, and the owner's
database was not mutated during closeout.

Reviewed documentation against the supplied logs, preserving the distinction between
owner live evidence and agent tests. This closeout changes documentation only;
no runtime, schema, dependency, CI, or lint configuration changes.

Top three remaining risks:

1. Editorial channel selection, upload caps, and rejection of incomplete Wikipedia
   history limit coverage. Successful collection does not establish factual truth.
2. Purging cannot run while the application is stopped. Schedule a daily purge and
   matching backup retention before unattended YouTube collection.
3. Quota counters cover collectors sharing this database; external tools can consume
   the same Google project's quota. Cache updates assume a single collector.

With exported settings, inspect the result using `offscroll status` and
`offscroll check-data`; collect again with `offscroll run-all` when appropriate.
Local completion tag: `m3-done`. The owner pushes and merges; fresh CI is still
pending, not claimed green for the closeout commit. Stop here until owner `continue`.
Before M4 scoring, resolve the YouTube derived-metrics concern recorded in ADR 0001.

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
