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

Pending implementation and owner-authenticated live acceptance. The agent has
asked only for environment availability or owner-run commands, never key values.
No live success or green doctor will be claimed without evidence.
