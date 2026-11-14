# 0001: Sources for the MVP

Status: accepted
Date: 2026-11-14

## Context

Offscroll is a weekly digest that collects, ranks, and summarizes items from a
small set of sources. The MVP should be manageable for a beginner learning Python
backend development and data engineering, with limited cost and connector scope.

YouTube's `mostPopular` chart changed on 2025-07-21 to Music, Movies, and Gaming
charts. It therefore does not provide the general trending feed we originally
wanted. The existing probe remains a feasibility experiment.
[YouTube revision history](https://developers.google.com/youtube/v3/revision_history)

The source selection below is accepted. That status does not mean every planning
assumption or proposed implementation has been verified; qualifications and
follow-up work are recorded below.

## Decision

- Use **Hacker News** for community-ranked links.
- Use **Wikipedia pageviews** for attention signals.
- Use **YouTube Data API v3** with curated channels. The intended approach is to
  compute trends ourselves from periodic snapshots, subject to resolving the
  derived-metrics policy issue in Consequences before implementing that scoring.
- Defer **news RSS** and **Google Fact Check API** until after the MVP.
- Limit MVP verification to **cross-source corroboration**. Agreement across
  sources is supporting evidence, not proof that a claim is true or independently
  fact-checked. Keep source links and distinguish corroborated from unchecked claims.
- Avoid `search.list` in the MVP; use the curated channel list to constrain discovery.

## Alternatives considered

- **Instagram/Facebook — rejected for the MVP.** The planning notes describe
  Graph API access as limited to managed business/creator accounts, with app
  review and a cap of 30 unique hashtags per rolling seven days for hashtag search.
  These specific scope and limit claims remain **unverified in this draft**:
  Meta's [hashtag reference](https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-hashtag-search/)
  could not be retrieved. Do not treat the managed-accounts-only wording as a
  verified restriction across all Meta APIs. Recheck current access requirements
  before reconsidering a connector.
- **Reddit — rejected for the MVP.** Reddit's migration announcement says new
  public API access requests stopped being accepted on 2026-10-31; this was not
  the shutdown date for all existing access. Remaining public API access is
  scheduled to end in March 2027.
  [Official migration announcement](https://www.reddit.com/r/redditdev/comments/1wubcvf/moving_data_api_apps_to_the_developer_platform/)
  The notes describe free access as non-commercial only. Current guidance requires
  approval for Data API access and permission plus a contract for commercial use;
  we should not assume an available self-serve free tier.
  [Reddit access guidance](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data)
- **X — rejected for the MVP; possible optional connector later.** Current docs
  confirm pay-per-use access with prepaid credits. We will not budget around a
  permanent free tier; promotional credits are not an ongoing free tier. The
  February 2026 start date in the planning notes was not independently verified.
  [X pricing](https://docs.x.com/x-api/getting-started/pricing)
- **News RSS and Google Fact Check API — deferred.** Both expand connector and
  verification work beyond this first implementation.

## Consequences

- Three sources keep development focused, at the cost of narrower topic coverage.
  Curated YouTube channels introduce selection bias and require maintenance.
- **Retention:** stored YouTube API data must be refreshed or deleted within
  30 days. A retention job is required before introducing persistent collection.
  Historical public statistics cannot simply be kept indefinitely.
  **Derived metrics:** YouTube policy section III.E.4.h restricts creating new
  metrics from API data; section III.L describes additional permissions for
  audited analytics use cases. Our proposed snapshot-based trend score needs
  resolution against these rules before implementation. Source selection alone
  does not establish permission to compute it.
  [YouTube developer policies](https://developers.google.com/youtube/terms/developer-policies)
- **Quota correction:** the notes state that `search.list` costs 100 units versus
  1 for most calls. The current reference instead lists 1 unit in a separate
  Search Queries bucket and 100 calls per day. Keep search out of the MVP for
  scope control, and check the project's actual quota before implementing later
  discovery features.
  [Current search.list reference](https://developers.google.com/youtube/data/reference/rest/v3/search/list)
- State retention rules for Hacker News and Wikipedia when their connectors are
  designed, before persisting their data. No retention period is assumed here.
- Link to originals instead of copying article text or images. Do not download
  videos, scrape YouTube, or store audiovisual files.
- Cross-source corroboration can repeat a shared error; source agreement must not
  be presented as verified truth. Dedicated fact-check integration remains deferred.
- This record documents future direction only; it does not add connectors,
  snapshot storage, ranking, a retention job, or change the existing probe.
