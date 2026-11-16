# YouTube export incident — 2026-11-17 (Asia/Tashkent)

## Evidence captured BEFORE code changes

Branch m6-youtube-fix starts at m5-delivery / 7f629df. Working tree was clean.
Observation time: 2026-11-16 19:06:53 UTC (2026-11-17 00:06:53 Asia/Tashkent).
Only read-only SQL was run against the existing offscroll-postgres-1 container;
no database mutation, credential inspection, .env read, or API request occurred.

| Stage | Evidence |
| --- | --- |
| a. status | `offscroll status` in the agent environment exits 1 with invalid_configuration: DATABASE_URL and YOUTUBE_API_KEY are both absent (presence booleans only). Equivalent read-only DB queries show YouTube run 18 succeeded, 98 fetched, 0 rejected, finished 2026-11-16 09:18:38 UTC, no error. Snapshot freshness 9.80 hours. Quota 27 units on Pacific date 2026-11-16; previous day 142. |
| b. channels | 25 cached, 25 active, 25 nonempty/valid uploads playlist IDs, 25 distinct playlists. All 25 configured active handles resolved; no missing mapping. Newest channel refresh 2026-11-15 15:01:47 UTC. Exact API playlist IDs stay in the database, not permanent Git incident history, to preserve the 30-day retention boundary. |
| c. raw/errors | 122 YouTube responses, 0 non-200 rows; newest 2026-11-16 09:18:38 UTC. No persisted quotaExceeded/keyInvalid/restriction/403 payloads. This does NOT prove no historical API errors: fetch failures roll back payloads. Runs 7/8 have only source_error; runs 9/12/15/18 succeeded. |
| d. video items | 104 videos; 73 published within seven days, 101 within fourteen. All 104 have snapshots; 98 have explicit privacy status, 104 have explicit embeddable booleans. Six legacy records lack privacy status. |
| e. seven-day funnel | 104 total → 73 age-eligible (31 removed) → 73 fresh item/snapshot (0 removed) → 71 explicit status (2 removed) → 71 public (0 removed) → 70 embeddable (1 removed) → 70 with channel/views (0 removed) → 18 unique channels (52 additional videos removed) → 4 slots (14 channels beyond cap). Fourteen-day eligibility is 95 videos; widening is unnecessary. |
| f. stored digest | Owner DB latest rolling digest 1 was built 2026-11-16 09:18:38 UTC and has 15 items, including FOUR YouTube items. Window: 2026-11-09 09:18:38 through 2026-11-16 09:18:38 UTC. |
| f. exported artifact | site/digest.json exported_at is 2026-11-16 15:34:49 UTC; lanes are HN=6, Wikipedia=5, YouTube=0. HTML contains the YouTube heading, zero watch links, and the generic “No eligible selections in this edition.” empty state. |

## Hypotheses and conclusion

- **Confirmed:** the workspace site was overwritten by the M5 fresh-clone
  two-source acceptance export. PROGRESS.md records that run and its deliberate
  lack of YouTube credentials. It is not an export of the owner's current DB.
- **Contributing diagnostic gap:** export has no saved-digest provenance; status,
  run-all and build do not make an empty-lane/export mismatch obvious enough.
- **Legacy status rows:** present, but only two remove seven-day candidates;
  70 eligible videos remain. Do not infer public status for those legacy rows.
- **Thin uploads/overstrict seven-day filter:** disproved for this incident.
  Keep seven days; do not change ranking to conceal an artifact mismatch.
- **Quota guard:** disproved at observation (27 versus the 7,999 local ceiling).
- **Invalid/rotated/restricted key or disabled API:** not established. The last
  authenticated run succeeded. A current API request requires the owner's
  credential environment; absent agent variables say nothing about key validity.
- **Template missing section:** disproved; the section and generic empty state
  are present. Improve the wording and preserve the source-specific section.

## Repair and validation

Implementation passes 201 unit and 39 PostgreSQL integration tests, Ruff and strict
mypy. The first owner terminal attempt stopped before collection with
invalid_configuration. After that, the owner explicitly authorized reading local
configuration. The agent ran live acceptance inside a child process that loaded
.env only internally, redacted credentials, and never emitted its contents. No
application default was changed to load dotenv; Gemini was disabled for this run.

The first authenticated attempt succeeded for YouTube (run 21: 97 fetched, zero
rejected, 52 quota units), disproving invalid-key/restriction/API-enablement
hypotheses. Wikipedia independently failed on the November 11 daily top list.
Repeated direct checks confirmed HTTP 404 for that discovery date, 200 for November
12 (1,000 articles), and a complete 35-day per-article series. ADR 0013 permits
one unavailable discovery day with a visible warning, while preserving complete
article metrics. Two unavailable discovery days or an article HTTP failure remain
fatal. No dates or zero counts are invented.

Final agent-run acceptance finished **2026-11-16 19:32:17 UTC**, November 17 local:

| Source | Run | Status | Fetched | Upserted | Rejected |
| --- | --- | --- | ---: | ---: | ---: |
| Hacker News | 22 | succeeded | 614 | 614 | 0 |
| Wikipedia | 23 | succeeded | 5,973 | 58 | 2 |
| YouTube | 24 | succeeded | 97 | 97 | 0 |

Wikipedia fetched includes discovery-list entries; two incomplete article series
were rejected. The six-of-seven discovery coverage warning was emitted explicitly.
YouTube used 27 units this run, 106 total for the current Pacific quota date.
run-all and its data checks, build-digest, export-site and doctor each exited zero.

Final `lane_funnel` (identical in build and doctor):

```json
{"total":113,"age":82,"snapshot":82,"freshness":82,"status":80,"public":80,"embeddable":79,"channel":79,"views":79,"unique_channels":19,"selected":4,"removed_age":31,"removed_snapshot":0,"removed_freshness":0,"removed_status":2,"removed_public":0,"removed_embeddable":1,"removed_channel":0,"removed_views":0,"removed_unique_channels":60,"removed_selected":15}
```

Doctor: `ok=true`, DB connected, schema 0004 at head, data_quality passed, all
sources healthy, key present (boolean only), quota 106/7999. Candidate counts:
HN 614, Wikipedia 67, YouTube as above. Latest digest 1 generated at
2026-11-16T19:32:14.518102+00:00 contains 6 HN + 5 Wikipedia + 4 YouTube entries.
Export provenance, complete public JSON and rendered HTML match that saved digest.
An additional artifact assertion confirmed all four real video links appear in
site/index.html and each public YouTube entry contains only lane_rank/video_id/url.
No derived YouTube metric, score, category or copied API metadata is exported.

Regression coverage includes SQL funnel boundaries and lane isolation, NULL scores,
channel caps, visible empty states, stale/wrong exports, auth failure via
MockTransport, safe reason codes, doctor failures and healthy operation. No tests,
lint rules or CI checks were weakened. The sandbox's ASGI test client stalled; the
same offline make check passed outside it. Integration used a separate disposable
PostgreSQL container, which was removed. No new dependency or migration.

## Five-line root-cause report

1. Root cause: the M5 two-source test export overwrote site/, while the owner DB already selected four YouTube videos.
2. Missing export provenance hid the mismatch; provenance checks, doctor, safe failures and visible empty states now expose it.
3. Live YouTube refresh succeeded: 113 total → 82 recent → 80 explicit status → 79 embeddable → 19 channels → four rendered links.
4. All live commands and doctor passed; make check passed 201 tests and make test-integration passed 39; seven-day YouTube eligibility stays unchanged.
5. Remaining risks: reduced Wikipedia discovery coverage, point-in-time health/concurrent publication, and YouTube policy interpretation; see ADRs 0008, 0012 and 0013.
