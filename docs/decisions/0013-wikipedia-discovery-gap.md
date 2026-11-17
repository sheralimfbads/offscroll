# 0013: Bound incomplete Wikipedia discovery without inventing metrics

Status: accepted
Date: 2026-11-17 (Asia/Tashkent)

## Context

M6 live acceptance refreshed YouTube successfully but Wikipedia failed. The
2026-11-11 daily top-list endpoint repeatedly returned HTTP 404, describing valid
dates whose data is unavailable. The adjacent 2026-11-12 list returned 1,000
articles, and a per-article request returned all 35 daily points. The discovery
gap is separate from the YouTube export incident.

## Options and decision

Fail the whole source on any discovery gap; use an older observation window; or
accept a bounded reduction in discovery coverage. Choose the last under the
owner's full-control directive. Request all seven top lists, allowing at most one
404 with explicit date and coverage warnings. Require at least six successful
lists. Any other HTTP error, malformed list, or empty candidate pool still fails.
No blind retry of a 404, replacement day, or synthetic zero is introduced.

Top-list totals only discover up to 60 candidates. Every saved topic still requires
its complete, consecutive 35-day article series: exact seven-day views plus a
disjoint 28-day baseline. A missing article request remains fatal; incomplete
series remain rejected. Missing discovery responses are not saved as successful
raw payloads. Preserve serial pacing even if the first request fails.

This amends M3's requirement for seven daily discovery responses only. Ranking,
freshness, metric validation, and source isolation are unchanged. No dependency.

## Residual risk and fallback

A topic prominent only on the missing discovery day may be overlooked. Logs and
raw successful response dates expose coverage; success means bounded discovery
with complete accepted metrics, not exhaustive coverage. Two or more unavailable
lists fail collection and doctor until an upstream recovery and successful rerun.
Do not substitute stale windows or manufacture counts to make health green.

## Official sources verified 2026-11-17

- [Wikimedia Analytics troubleshooting](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/troubleshooting.html):
  404 can mean zero or not-yet-loaded data, which the API cannot distinguish;
  time-series gaps also occur. Our conservative parser never assumes a gap is zero.
- [Page view analytics reference](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html):
  most-viewed-page discovery and per-page view history are separate endpoints.

Offline MockTransport tests cover one missing discovery day, pacing after the first
404, two/all missing days, auth failure, article-history 404, and unchanged exact
weekly counts. Existing tests reject incomplete and duplicate series.
