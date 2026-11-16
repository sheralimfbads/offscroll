# 0007: Expire YouTube observations independently and check every enabled source

Status: accepted
Date: 2026-11-15

## Context

YouTube data has a different retention rule from HN and Wikipedia. A recently
refreshed item must not keep its old snapshots indefinitely. Collection failures
must remain visible without preventing other sources from running.

The [official YouTube developer policies, III.E.4](https://developers.google.com/youtube/terms/developer-policies)
were checked 2026-11-15: public statistics cannot be retained beyond thirty days;
other non-authorized API data must be refreshed or deleted within thirty days.
This is our conservative engineering interpretation, not a claim of legal approval.
The owner must read the policies before public launch. Derived scoring remains
unresolved for M4; hiding a derived metric would not resolve the restriction.

## Decision

Keep HN and Wikipedia raw responses ninety days. For YouTube, delete raw responses
at thirty days, delete each old snapshot by its own capture time, delete items
whose metadata was not observed within thirty days, and delete channel-cache
entries by refresh time. Item deletion cascades to remaining snapshots. Operational
run logs and quota reservations contain our counts/categories, not copied video
metadata, and remain. Replay first purges expired input, so it cannot resurrect it.

`purge-raw` is the network-free purge job for all these layers. Run it before
`run-all`, YouTube collection, and raw replay in an independent transaction, so
later failures do not undo deletion. A stopped application cannot execute cleanup:
operators must schedule the purge at least daily before unattended collection and
include database backups in the same retention policy. Hosting and schedules are
still owner-controlled M5 work; no scheduler is silently installed here.

Enable sources explicitly with `OFFSCROLL_SOURCES`, defaulting to all three.
`run-all` attempts each source independently and returns failure if any source or
final data check fails. `status` reads last attempts, snapshot freshness, row counts,
and quota. `check-data` requires a successful last attempt, nonempty items with
snapshots, data fresher than 36 hours, required fields, unique identities, sane
snapshot values/source associations, and no expired YouTube data. Checks do not
perform network calls or modify records. No new dependency is needed.

## Alternatives considered

- Purge only raw responses: violates the snapshot/core retention requirement.
- Reset old snapshot ages when refreshing an item: misrepresents historical data.
- Silently skip unconfigured/failing sources: produces misleading green status.
- Run live checks in CI: leaks service variability and credential requirements
  into repeatable tests; manual acceptance remains separate.

## Consequences

Failures are explicit, and a source outage does not suppress other source attempts.
A legitimate empty candidate set fails quality checks until the owner investigates.
Data checks use observation freshness; Wikipedia's latest complete data day is also
recorded in item metadata. They cannot establish factual accuracy or comprehensive
coverage. Historical YouTube observations disappear as intended. Retention cannot
be guaranteed through extended downtime without an external scheduled purge and
backup lifecycle; do not advertise unattended operation until those are configured.
