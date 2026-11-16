# Offscroll progress

Last resume check: 2026-11-16 (Asia/Tashkent). Full-control directive accepted.
M4 is tagged locally at af171fc (m4-done). M5 implementation is under final
validation on m5-delivery; no pushes or publication occurred.
Scope and working rules: [PROJECT_BRIEF.md](PROJECT_BRIEF.md).
The brief's M4 section contains the owner's 2026-11-16 lane amendment; its original
mission date remains historical. Use the date above for this resume check.

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
  - [x] Owner: merged M3 into main at `35429cb`; automation did not push.
- [x] M4: Ranking, corroboration, persisted digests, and summaries.
  - [x] Accept the owner-selected YouTube lane design in ADR 0008 and the brief.
  - [x] HN/Wikipedia scoring, clustering, selection, config, and offline fixtures.
  - [x] Isolated YouTube SQL ordering, one per channel, no stored/rendered ratio.
  - [x] Migration 0004, atomic digest replacement, CLI lanes and explanations.
  - [x] Retention-aware YouTube display and link-only archives; template summaries.
  - [x] Local checks, PostgreSQL tests, migration round trip, real two-source build.
  - [x] Verify two LLM provider options and prepare ADR 0009.
  - [x] Owner chose Gemini free tier; ADR 0009 accepted.
  - [x] Implement Gemini, validate cache/cap/fallbacks, close locally with `m4-done`.
  - [ ] Owner: push M4 and obtain fresh CI; automation never pushes.
- [ ] M5: Delivery, deployment decisions, runbook, and portfolio polish.

At the initial M2 audit no historical completion tags existed; M2 closeout added `m2-done`.
The owner authorized M3 after merging M2 to main at `b9c906d`.

## Repository state and evidence

- Current branch: `m5-delivery`, created from M4 tip `af171fc`.
- M4 branch/tag remain at `af171fc`; M3 main merge is `35429cb`.
- This implementation turn began clean at preflight commit `b90ef24`. Local and
  cached remote main both point to `35429cb`, consistent with the owner's merge
  confirmation. No remote fetch or push was needed.
- M2 implementation commits: `2925358`, `fcff60f`, `8573c66`, `df9e49e`.
- Migrations: `0001_ingest_runs.py`, `0002_hackernews.py`, `0003_sources.py`,
  and the new `0004_digests.py`;
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
- 2026-11-16: full-control directive supersedes milestone/decision stops; continue
  through M5, never push, keep billing and schedules disabled.
- On 2026-11-15 the owner delegated the CI credential choice. Keep the public
  disposable test password as a narrow exception; real API/production credentials
  still require GitHub Actions secrets. This preserves fork PR testing without
  granting access to persistent data. The brief remains verbatim.
- Record the API/retention design in [ADR 0002](decisions/0002-hackernews-ingestion.md),
  transaction trade-offs in [ADR 0003](decisions/0003-run-transactions.md), and the
  Python pin, offline tests, manual smoke, and CI exception in
  [ADR 0004](decisions/0004-runtime-and-ci.md). No dependencies, applied migrations,
  CI configuration, or lint rules changed during closeout.

- 2026-11-16: ADR 0009 accepts stable Gemini 2.5 Flash-Lite, reviewed inputs,
  durable 50/day cap, template public delivery, and no billing.

- 2026-11-16: ADR 0010 selects GitHub Pages, public templates/video links, and
  optional read-only FastAPI; ADR 0011 selects filtered seven-day backups.

## Open questions / owner actions

1. Owner creates/configures any required accounts, keeps Gemini billing disabled,
   supplies credentials outside chat, and runs optional live authenticated smoke.
2. Owner pushes/merges; no remote CI or deployment is claimed locally.
3. M5 defaults: GitHub Pages static export, disabled schedule, license deferred.
   Exact owner steps belong in docs/OWNER_TODO.md; do not stop local work for them.

## M4 completion report (P1)

Gemini adapter implemented behind Summarizer with stable configurable
`gemini-2.5-flash-lite`, header-only masked credentials, reviewed public input hashes,
Pydantic JSON validation, neutral two-sentence limit, immediate template fallbacks,
success cache before requests, token/model/prompt recording, and a durable atomic
50-attempt UTC daily cap. No new dependency/schema migration was necessary: the
existing quota table has a distinct gemini row. Billing and visitor-triggered LLM
calls are absent. Public delivery conservatively uses templates because offline
batching does not establish a regional-terms exemption. ADR 0009 records official
URLs/dates and the Groq-then-template operational fallback (no automatic second
processor). No live Gemini request or .env read occurred.

Validation: make check passed (163 unit tests, 32 integration deselected; Ruff and
strict mypy). make test-integration passed 32 tests against disposable PostgreSQL;
cap durability, cache reuse, fake injection/HTTP errors, malformed JSON, approval
privacy boundary and secret masking are covered. Database/storage cleaned up.
P0 live acceptance remains the 11-item public-source digest recorded below.

Self-review risks: (1) semantic privacy depends on exact-input human review;
(2) a key cannot establish billing/project-region settings, which remain owner
responsibilities; (3) valid model JSON may still contain inaccurate prose.
Fallbacks keep collection/build usable. Local tag m4-done closes M4; proceed
immediately onto m5-delivery. No push, billing, account creation or live secret use.

## Historical M4 P0 report (provider choice subsequently resolved)

The owner merged M3, rebased this branch, and selected an isolated YouTube lane
on 2026-11-16. ADR 0008 and the M4 brief now record that accepted amendment,
including official policy/branding URLs and verification dates. The previous
exclusion proposal was not implemented.

Implementation commits: `c4e9546` (ranking/design) and `98fb61b`
(persistence/CLI/retention), followed by the validation/provider-decision record.

Built deterministic HN/Wikipedia percentiles, complete-link title/URL clustering,
corroboration, lane/publisher caps, and explainable config snapshots. YouTube is
ordered only within its SQL query; the ratio never leaves `ORDER BY`. Caps are
6 HN, 5 Wikipedia, 4 YouTube, one video per channel; short lanes remain short.
The new migration adds digests, items, and summary-cache tables. Database checks
reject YouTube scores, clusters, summaries, copied titles/counts, and malformed
link payloads. YouTube titles retain their exact API whitespace after refresh.

`build-digest [--week]` atomically replaces the selected window; rolling and ISO
keys are separate. `digest` and `explain-digest` render labelled source sections;
the former M2 query is `top hackernews`. Templates provide source context with
input-hash reuse and zero tokens/cost. YouTube archives store only ID/link and
hydrate current metadata while both archive and API data are younger than 30 days.
The purge detaches expired archive references even for recently refreshed videos.

Validation on 2026-11-16:

- `make check`: Ruff and strict mypy passed (18 source files); 144 unit tests
  passed, 30 integration tests deselected.
- `make test-integration`: 30 passed, 144 deselected in 4.34s against disposable
  PostgreSQL 18.7, with mocked HTTP.
- Migration upgrade to 0004, downgrade to 0003, then upgrade to 0004 passed.
  Applied migrations 0001–0003 were not changed.
- Real HN/Wikipedia collection in a separate disposable database succeeded:
  623 HN items and 58 Wikipedia topics. Two builds returned the same digest ID;
  the saved digest contained 11 items, HN=6/Wikipedia=5/YouTube=0. This meets the
  real-build acceptance of 10–15 items across at least two sources. It is not a
  claim of live YouTube acceptance for M4.
- Seeded integration acceptance produced all 15 slots (6/5/4), verified one video
  per channel, lane isolation, NULL YouTube scores, rollback on failed rebuild,
  metadata expiry, one-day age floor, explicit public-status eligibility, and cache reuse. The exact-expiry test uses the PostgreSQL
  transaction clock to avoid comparing against a slightly later Python timestamp.
- Temporary containers/storage were removed. No `.env` or existing API key was
  read; the owner's database was not changed. No dependencies, CI, or lint
  configuration changed. HTML export and graphical branding remain M5 scope.

Self-review checked formula bounds/ties, untrusted-title escaping, SQL-only video
ordering, JSON schema constraints (including JSON null), transaction rollback,
window identity, and reference cleanup. Top three risks:

1. YouTube policy wording retains the uncertainty accepted in ADR 0008. Stored
   status reflects the last API observation; collection must refresh it. Fallbacks
   are chronological videos or an API Compliance Audit, not a hidden shared score.
2. Coverage is limited by collection and matching heuristics. HN/Wikipedia use
   current metadata/observations, so historical rebuilds are not point-in-time
   reconstructions, and source agreement cannot establish factual truth.
3. Cleanup cannot run while the app is stopped. Daily purge, backup expiry, and
   retention-aware M5 exports remain necessary before unattended publication.

Try with exported settings:

```bash
make migrate
.venv/bin/offscroll build-digest
.venv/bin/offscroll digest
.venv/bin/offscroll explain-digest
.venv/bin/offscroll build-digest --week 2026-W46
.venv/bin/offscroll digest --week 2026-W46
```

Historical note, superseded by the M4 P1 report above: M4 was open at the brief's LLM-provider decision. ADR 0009 compares Google
Gemini and Groq using current official pricing, free limits, and terms. Provider
requests, fake-provider validation/fallback tests, and a hard daily call cap are
pending the choice, not silently claimed complete. No `m4-done` tag yet and no
M5 work started. The owner may choose a provider or explicitly defer P1.

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
