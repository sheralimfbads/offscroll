# How digest selection works

The digest has separate **Hacker News**, **Wikipedia**, and **YouTube** sections.
Only ranks inside each section are meaningful. Limits are 6, 5, and 4 items
respectively; empty slots are not transferred. More coverage is not evidence of
truth or independent verification.

## Windows and rebuilds

`offscroll build-digest` uses the preceding 7 × 24 hours in UTC. Rebuilding on
the same UTC date replaces that rolling digest. The exact timestamps and ranking
configuration are saved in `config_snapshot`. `--week 2026-W46` selects an ISO
week from Monday 00:00 to the following Monday 00:00 UTC. A current partial week
is allowed, a future week is rejected. Rolling and ISO builds have separate keys;
a repeated ISO build replaces that week atomically. Readers never see half a build.

HN dates mean publication; Wikipedia dates mean the end of its seven-day
observation window. HN windows include the start and exclude the end; Wikipedia
includes the observation ending at the week boundary. A build uses the latest
available observations and current catalog metadata, not a reconstruction of
what was known historically. Wikipedia keeps only its latest topic baseline in
core metadata, so old week rebuilds can lose candidates after later collection.
Archived HN/Wikipedia entries preserve their build-time selection and context.

YouTube candidates must also be published within seven days of the build clock,
public and embeddable per the stored API status, and have a view count. Future
publication/observation dates and metadata or observations aged 30 days are
excluded. Old ISO-week rebuilds therefore do not repopulate old YouTube videos.
Existing M3 rows need one normal collection refresh to supply explicit public
status and preserve exact title whitespace. No credentials are needed to build.

## HN and Wikipedia only

For a source's candidate pool, a percentile is the zero-based average position
in its sorted nonmissing values, divided by `n - 1`. Ties get the average position;
a singleton gets 1; a wholly tied pool gets 0.5. Missing/nonfinite values get 0
and do not contribute to the denominator. A missing Wikipedia spike (zero baseline)
therefore does not become infinity.

- HN momentum = `0.6 × pct(points) + 0.4 × pct(comments)`.
- Wikipedia momentum = `0.5 × pct(7-day views) + 0.5 × pct(spike_ratio)`.
- `spike_ratio = (7-day views / 7) / mean daily views in the preceding 28 days`.
- Final score = `momentum × min(1.3, 1 + 0.15 × (distinct_sources - 1))`.

Weights and similarity threshold live in `config/ranking.yaml`; weights must
sum to one for each source. The config cannot increase the owner's slot caps.
Momentum is in [0,1]; the final score may reach 1.3 (currently 1.15 with two sources).

Titles are Unicode-normalized, case-folded and split into word tokens, with a
small explicit stop-word list. Cross-source pairs match at token Jaccard ≥ 0.5,
or an equal canonical URL. A shared domain needs at least two shared tokens and
Jaccard ≥ half the configured threshold; a publisher alone is insufficient.
Canonical URLs drop fragments, `www.`, and trailing slashes but retain queries.

Groups use deterministic complete-link matching: every member must match every
other. Same-source items do not cluster. This prevents transitive chains from
joining unrelated stories. Keep the highest-scoring representative, listing the
other as "also covered by"; ties use newer publication time, source, external ID.
Select into the representative's lane, with max two HN entries per external
publisher. Wikipedia itself is the source, so its domain does not cap topics.
A lane with independent eligible representatives gets entries; if all its items
lose to another lane's cluster representatives, it may be empty. We never duplicate
a cluster or violate caps solely to fill a lane.

## YouTube only

YouTube never enters the functions above, including corroboration. Within its
own query only, sort by `views / max(age_in_days, 1)` descending; age is elapsed
UTC seconds from the API publication timestamp to the build clock divided by
86,400. Tie-break by newer publication then video ID. Select at most one per
channel and four total. Missing views exclude a video rather than becoming zero.

The ratio appears only in SQL `ORDER BY`. It is neither selected into the query
result nor stored or rendered. `final_score` is NULL; breakdown and cluster are
empty; there is no YouTube summary. No curated category or suitability claim is
shown. Recent reads show the current API title, thumbnail URLs and exact integer
counts, with no abbreviations or calculated replacement counts. Missing counts
remain null. The archived payload contains only video ID and YouTube URL from
day one; after 30 days the reader stops hydrating metadata and purge detaches the
item reference. Structural lane rank is retained; no historical API metadata is.

The accepted interpretation, official URLs, dates, branding requirements and
fallbacks are in [ADR 0008](decisions/0008-m4-youtube-scoring.md). The M4 CLI
prints labelled sections; M5 must add the official graphical attribution alongside
the YouTube section without changing titles or thumbnail images.

## Summaries and limitations

`TemplateSummarizer` supplies deterministic source context without claiming to
have read the linked article or executing title text. The label is **Source
context**, not AI-generated. HN/Wikipedia summary rows record input hashes, model
`template`, prompt version, zero tokens and zero cost; rebuilds reuse identical
inputs. YouTube is excluded. Choosing an LLM remains a separate owner decision.

Candidate pools reflect source collection limits and editorial channel choices.
Percentiles measure relative attention in those pools, not quality. Title matching
can miss synonyms and join different events with similar wording. Source agreement
may repeat one shared error. No model or matching heuristic verifies claims.

## M5 public delivery boundary

The static HTML/JSON and optional web API show separate source lanes using the
same saved selection. Public YouTube entries contain only video ID/link from day
one; local CLI reads can show fresh unmodified API metadata. Public summaries use
deterministic context templates, while reviewed Gemini output remains local.
This trades richer previews/prose for enforceable archive retention and conservative
regional policy handling; see ADRs 0009–0011 and COMPLIANCE.md.
