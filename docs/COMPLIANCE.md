# Compliance implementation map

Reviewed 2026-11-16. This maps project controls to code/tests; it does not certify
legal compliance or factual accuracy. Official URLs/dates and residual policy
interpretations live in ADRs 0002, 0005–0011. Owners must reread current terms before
launch. Tests use fake providers; live authenticated acceptance is separately noted
in PROGRESS.md.

| Source / rule | Enforcement | Evidence |
| --- | --- | --- |
| YouTube: official API, curated uploads, no search.list/scraping/media downloads | `connectors/youtube.py`: channels, playlists, batched videos; header authentication | `test_youtube_connector.py`: request path/auth, batches, cache tests |
| YouTube: public/embeddable, seven-day digest eligibility | SQL selection in `digests.py` | `test_digests_integration.py`: eligibility, unconfirmed status, age floor |
| YouTube: isolated lane, no shared scoring/clustering/also-covered or derived metric storage/display | `digests.py` query-only ORDER BY; `ranking.py` HN/wiki only; migration 0004 constraints | three-lane isolation and database rejection tests in `test_digests_integration.py`; `test_ranking.py` |
| YouTube: four slots, one per channel, no backfill | query selection and fixed lane caps | three-lane and selection tests |
| YouTube: unmodified API title/counts/thumbnail URLs in local fresh display | `connectors/youtube.py`, `digests.py` allowlist; no category labels | exact preservation test in `test_youtube_connector.py`; stored/rendered digest tests |
| YouTube: delete/refresh within 30 days, ID/link-only archive | `retention.py`, retention-aware `read_digest`; public `delivery.py` always links only | `test_sources_integration.py` retention tests; archive/expired metadata tests in `test_digests_integration.py`; `test_delivery.py` |
| YouTube: backups cannot extend API retention | `backups.py` excludes API tables/rows and detaches archive references | filtered backup/export integration test; real restore rehearsal |
| YouTube: distinguish source, attribution, official links, no safety/suitability claims | separate template section, official logo/name/link, no local category field | HTML/public projection tests; ADR 0010 brand provenance; owner visual review remains |
| YouTube: durable daily quota, safe errors | `quota.py`, connector pre-request reservation | `test_sources_integration.py` quota/rollback/diagnostic tests; `test_youtube_connector.py` |
| Wikipedia: official pageview API, descriptive contact User-Agent, serial pacing | `connectors/_http.py`, `connectors/wikipedia.py`; <=60 requests/min before latency | `test_wikipedia.py` serial/bounded fetch; HTTP request tests |
| Wikipedia: complete 35-day input, no invented missing values | pure parse rejects incomplete/invalid series; baseline explicitly unknown if zero | `test_wikipedia.py` series and zero-baseline tests |
| Wikipedia: bounded discovery coverage (ADR 0013) | require six of seven daily top lists; warn on one 404; all other failures propagate | `test_wikipedia.py` missing-list, auth, pacing and article-history failure tests |
| Wikipedia: attribution and 90-day raw policy | source notes, retention.py; CC0 pageview attribution; footer links Wikipedia and CC BY-SA article context | source/retention integration tests; template tests. No article extracts currently fetched |
| Hacker News: public API, polite bounded retries/paging, contact User-Agent | `connectors/hackernews.py`, `_http.py` | `test_hackernews.py` params, pacing, retries, truncation |
| Hacker News: originals/discussion links, no copied articles/images | validated URL fields, escaped delivery, source context templates | HN URL/parser tests; `test_delivery.py`; pipeline integration |
| Hacker News: 90-day raw policy | connector declaration, `retention.py`; backup 83+7-day bound | pipeline retention tests; backup tests |
| Gemini: stable free-tier model, configurable; no key means templates; no billing | `SummarySettings`, `configured_summarizer`; no billing API or visitor requests | config tests in `test_summaries.py`; owner must verify project billing remains disabled |
| Gemini: only public title/source/domain/description; no personal data, articles or YouTube | `public_input`, exact approval hashes, contact/credential filter | approved-field and review-filter tests; semantic privacy still requires human review |
| Gemini: untrusted inputs, Pydantic JSON, <=2 sentences, no “verified” output | system instruction + serialized data; `SummaryOutput` | injection, malformed JSON, schema/output tests in `test_summaries.py` |
| Gemini: any error/429 uses immediate template; cache; usage metadata; 50/day | `summaries.py`, `_store_summary`, independent durable quota transaction | fake HTTP/error tests; cache and durable cap integration tests |
| Gemini: label generated prose; free data may be reviewed/improve products; regional restriction | local `summary_label`; README privacy; public template projection and filtered backups | `test_delivery.py`, backup/export integration; ADR 0009 verified terms/regions |
| All: no secret logging/reading dotenv; offline tests | env_file=None, safe errors, HTTP mocks, git pattern scanner | config/CLI/source error tests; `tests/conftest.py`; history scan report |
| All: disabled automation, finite untracked page | commented schedule + variable guards, no scripts/cookies/visitor AI | `test_delivery.py`; workflow configuration tests |

Operational boundaries: deletion cannot run while the application is stopped;
owner enables daily purge and expires all downloaded backups. API observations
can become stale between requests. Pageviews and agreement are attention/context,
not proof. Free Gemini terms are not satisfied merely by a valid key or offline
batching; public delivery therefore uses templates. Static YouTube link-only
publication is intentionally less rich to avoid unenforceable CDN retention.

M6 adds `diagnostics.py` and shared `youtube_funnel` predicates: doctor is read-only,
reports only boolean credential presence, and checks saved/exported lane identity.
Regression coverage in test_diagnostics.py, test_digests_integration.py and
test_sources_integration.py covers wrong exports, stale HTML, NULL status,
rejection counts, auth failures, and preserved active-channel cache. Error reasons
are allowlisted in connectors/_http.py; remote messages/metadata never reach logs.
The seven-day lane remains unchanged; see ADRs 0008 (addendum) and 0012.

M7 (ADRs 0014–0015): public data remains YouTube ID/link-only. The visitor may
explicitly load the official privacy-enhanced player, with standard controls,
minimum 200×200 viewport, no automatic playback, and Referer identity. Tests in
tests/browser/reading.spec.mjs block external requests by default, assert none
before consent, inspect the official URL/referrer/dimensions after consent, and
check mobile layout plus WCAG A/AA in light/dark themes. Source text stays escaped;
no article text or video metadata enters browser preferences. Preferences can be
cleared, expire on a subsequent visit, and are never sent to the application.
Public privacy information describes Google's separate processing after consent.

Cloud source data is confined to the disposable runner DB. Public artifacts include
only presentation assets and allowlisted digest data. The per-run request cap and
conservative workflow-history budget are enforced by quota.py/cloud.py and covered
by test_cloud.py; the original daily DB guard remains. Workflow tests verify the
enablement gate, main-only collection, limited permissions, no Gemini/remote DB
secret, doctor-before-deploy and non-cancelling concurrency. Source-retention tests
remain in force for the persistent local path. Cloud run-history deletion, shared
keys and provider schedule availability remain operational limitations, not hidden
claims of guaranteed compliance or availability.
