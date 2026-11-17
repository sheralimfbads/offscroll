# 0012: Diagnose empty lanes and bind exports to saved digests

Status: accepted
Date: 2026-11-17 (Asia/Tashkent)

## Context and evidence

INCIDENT-youtube.md records pre-change, read-only evidence: the owner's database
had four selected videos and 70 eligible seven-day candidates, while site/ was
an M5 two-source acceptance artifact with zero videos. The section was present.
Widening selection or relaxing public-status requirements would conceal the real
problem. Both the agent and the owner's initial terminal attempt also lacked
usable exported configuration; a venv does not load environment settings.

## Options and decision

Re-export from the intended database, keep the seven-day isolated lane, and make
misconfiguration and stale/wrong exports detectable. Add read-only `doctor` for
DB connectivity, Alembic head, each enabled source's last success and freshness,
boolean-only key presence, quota, candidate funnel, saved-lane counts, and matching
HTML/JSON. It exits nonzero for missing/stale sources, empty enabled lanes,
missing/old provenance, quota ceiling, or an inconsistent export. It makes no API
calls and cannot establish that a merely present key is valid; run-all tests that.

Export JSON adds only digest ID and generation time, never database identity or
connection details. Doctor compares identity, complete public lane payload and
rendered HTML. Export checks identity before and after reading and asks for a retry
if a rebuild raced it. Files remain individually atomic; doctor detects partial
publication. A future all-directory atomic publisher is an operational enhancement.
Test/fresh-clone artifacts must stay in their own output directories; never copy
them over the owner's site/ as acceptance-test cleanup.

One code-owned SQL predicate list drives both YouTube selection and a sequential
funnel (age, snapshot, freshness, explicit status, public, embeddable, channel,
views, channel deduplication, slots). All values remain bound SQL parameters. Only
operational counts enter logs; the engagement ratio remains private to ORDER BY.
Empty lanes warn at build time and retain source-specific visible empty states.
No model, common scale, backfill, or schema migration is introduced.

Run-all preserves safe failure codes and remains nonzero on any source/quality
failure. Status highlights failure and exposes last success/freshness. Google
errors retain only allowlisted structured reasons, never bodies, messages, URLs,
headers, project metadata or credentials. Unknown stored error text is redacted.
API enablement/restriction errors remain distinct from quota exhaustion. Failed
fetch payloads are not persisted, so zero non-200 raw rows does not prove no error.

Pipeline review also fixes HN Retry-After handling, disables HN redirects even for
an injected client, rejects nonfinite retry delays, and keeps configured cached
channels active when API refresh fails. Existing three-attempt limits, finite
network/DB timeouts, independent durable quota reservations, savepoint rollback,
item uniqueness and per-run snapshots remain in force. No dependency was added.

## Official references verified 2026-11-17

- [YouTube API errors](https://developers.google.com/youtube/v3/docs/errors):
  forbidden and quota failures are different categories; 403 alone is not a diagnosis.
- [Google API ErrorReason](https://docs.cloud.google.com/dotnet/docs/reference/Google.Api.CommonProtos/latest/Google.Api.ErrorReason):
  structured reasons distinguish invalid keys and service/IP/referrer restrictions.
- [Google authentication troubleshooting](https://docs.cloud.google.com/iam/docs/troubleshoot-auth-manager):
  key restrictions/API enablement require owner-side project checks, not logging
  provider messages or disabling restrictions indiscriminately.

## Residual risks and fallback

Doctor is a snapshot of local health, not proof of future API availability or
credential validity. Unknown reasons remain generic. Empty lanes can be legitimate
and still require operator attention under the owner's strict doctor contract.
No source data or unreviewed model prose is added to public output; YouTube remains
ID/link-only. If live credentials are unavailable, complete offline checks and
report the owner-run acceptance as pending rather than fabricate videos or success.
