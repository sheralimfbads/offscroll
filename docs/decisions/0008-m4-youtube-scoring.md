# 0008: Resolve YouTube scoring before M4 implementation

Status: proposed; owner decision required
Date: 2026-11-16

## Context

M3 is complete locally at `de119e2` (`m3-done`). The owner requested continuation
to M4. Its required YouTube views-per-day percentile conflicts with the policy
concern recorded in ADR 0001. The brief requires stopping for conflicting
requirements; a general request to continue does not resolve this specific choice.

Official sources checked on 2026-11-16:

- [YouTube developer policies, III.E.4.h and III.L](https://developers.google.com/youtube/terms/developer-policies):
  the general rule restricts creating derived data or metrics from API data.
  Additional allowances concern audited analytics use cases with permission.
- [Additional policies for derived metrics and data storage](https://developers.google.com/youtube/terms/derived-metrics-policy):
  specific analytics metrics depend on the policy amendment and applicable use
  case. Examples of permitted metrics do not establish Offscroll's eligibility.

Our interpretation: views divided by age, its percentile, and the combined score
are derived metrics. Keeping them internal does not resolve the general rule.
No evidence of permission for Offscroll is recorded in this repository. Automated
title clustering also needs consideration under the broader derived-data wording;
simply replacing the views-per-day formula is insufficient to settle the design.

## Decision

Pending owner decision. Recommend deferring YouTube participation in the M4
digest candidate pool, scoring, clustering, summaries, and persisted digest data.
Keep the existing M3 collector and its retention enforcement intact.

Under this proposal, implement the remaining M4 ranking and digest requirements
for Hacker News and Wikipedia. Apply the source minimum only to eligible digest
sources. Preserve the six-per-source cap, so the maximum is 12 items with two
sources; the live acceptance target remains 10–12 items across both sources when
sufficient candidates survive selection. Never fill a shortfall with invented
items or silently relax diversity constraints. Use deterministic template
summaries by default; the separate LLM-provider choice remains a later stop.

This is a proposed scope adjustment, not an accepted amendment to the brief.
No M4 runtime code or schema change is authorized by this record alone.

## Alternatives considered

- Keep the original three-source design pending evidence of applicable YouTube
  permission. The owner would need to establish eligibility and approval; the
  agent must not submit an application or accept terms on the owner's behalf.
- Hide the computed score or label it as Offscroll's score. Neither establishes
  permission to create the metric, so this does not resolve the conflict.
- Add a separate editorial YouTube section. This requires a concrete selection
  design and another scope decision; it is not part of this proposal.

## Consequences

The recommended path permits a smaller digest without depending on uncertain
YouTube scoring permission, at the cost of video coverage and a 12-item ceiling.
The original three-source selection requirement remains unmet until the owner
accepts the scope adjustment or supplies a basis for the original design.
M4 is not complete, and no `m4-done` tag should be created for this preflight.
