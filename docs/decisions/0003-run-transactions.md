# 0003: Keep each pipeline run atomic and preserve ordinary failure records

Status: accepted
Date: 2026-11-15

## Context

M2 requires one transaction per run, replay without duplicates, and safe failure
logs. Partial raw/core writes would make counts and subsequent replay confusing.

## Decision

Create the run record in an outer transaction. Fetch, land raw pages, and transform
inside a savepoint. On an ordinary caught error, roll back the savepoint and commit
the failed run record with a fixed error category. Never format exception details
that could include credentials or payloads. Use bound SQL through SQLAlchemy Core.

Identify items by `(source, external_id)` and snapshots by `(item_id, run_id)`.
Upsert item metadata only when the observation is at least as recent as the stored
one. Preserve first-seen time. A replay uses the original run ID and fetch times;
a new run adds a new observation. The latest-metrics view breaks timestamp ties
by run ID. No applied migration is changed by this documentation closeout.
No new dependency is needed.

## Alternatives considered

- Commit each page separately: smaller transactions, but partial runs violate
  this milestone's atomicity requirement.
- Commit the run log independently: survives more crashes and exposes running
  status, but requires another transaction and reconciliation rules.
- Append duplicate items: easy writes, but requires deduplication in every reader.

## Consequences

Successful runs have consistent raw/core data; replay cannot add duplicate snapshots.
New runs deliberately add snapshots, so idempotence does not mean identical row
counts across different run IDs. The transaction stays open during HTTP requests.
Other connections cannot see `running` until completion, and a process crash or
lost connection can remove the entire run record. Replaying a run updates its
status rather than preserving a separate attempt history. These are explicit M2
trade-offs; stronger operational auditing needs a later design decision.
