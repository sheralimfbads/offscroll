# 0011: Filtered, short-lived backups and disabled automation

Status: accepted
Date and official-source retrieval: 2026-11-16

## Context and options

A full pg_dump would copy YouTube API metadata into backups and extend its
retention. Encrypted full backups still retain that data. Rather than inventing
an exception, omit it. SQL recovery is useful for the rest of this small project.

## Decision

Use PostgreSQL 18.7 `pg_dump --schema-only`, then safely quoted INSERT statements
from a repeatable-read snapshot in dependency order. Exclude YouTube source items,
snapshots, raw responses, run records and channel cache. Keep archive video IDs/
links with detached item references, plus operational quota counters. Preserve
HN/Wikipedia template summaries/digests; omit model-generated summaries and detach
their references to avoid publishing local Gemini output in public artifacts; include only raw responses newer than 83 days.
Expire backups at seven days, so those raw copies stay within the 90-day policy.
Use files with mode 0600, no overwrite, and restore only into an empty database.
Never migrate while backing up: schema and data use separate connections.

The disabled pipeline makes a backup each collection run (every six hours when
enabled, exceeding the daily requirement), with artifact retention of seven days.
Local owners run expire-backups daily. Artifacts are not a durable disaster-recovery
service: owners must check job success and periodically rehearse restore. Never
publish database backups on Pages; a public repository's Actions artifacts are
not a private backup vault. This backup contains only public-source records and
local operational data, but owners wanting restricted access must use a private
repository or private backup destination. No secrets belong in database rows.

Docker supplies matching pg_dump/psql binaries. Passwords are inherited through
PGPASSWORD, never command arguments or printed diagnostics. Linux host networking
is required for this helper (also available in suitably configured Docker Desktop).
A trusted SQL backup can execute code: restore only one's own trusted backup into
a disposable target first. Restore refuses nonempty targets rather than dropping
anything. No dependency or migration was added for these operations.

Sources: [pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html),
[transaction isolation](https://www.postgresql.org/docs/18/transaction-iso.html),
[workflow scheduling](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule),
[artifact access/retention](https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts).

## Residual risk and fallback

A restore deliberately requires recollecting YouTube metadata. Backups are not a
complete replica; future tables require an explicit filter decision and test.
Schema/data snapshot coordination requires an operational migration pause.
If scheduled execution is unavailable, collect, purge, build and back up locally;
keep static publication separate. Never silently retain full API backups instead.
