# 0009: Use Gemini free tier for reviewed offline summaries

Status: accepted
Date: 2026-11-16

## Context and verified sources

The owner selected Google AI Studio/Gemini free tier and delegated subsequent
implementation decisions. Billing must NOT be enabled. Verification 2026-11-16:

- [Model](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-lite):
  `gemini-2.5-flash-lite` is explicitly Stable, supports structured output, and
  is distinct from the shut-down preview variant.
- [Pricing](https://ai.google.dev/gemini-api/docs/pricing): text free tier is
  available. Listed paid equivalents per million input/output tokens are
  $0.10/$0.40 for 2.5 Flash-Lite, $0.25/$1.50 for 3.1 Flash-Lite, and $0.30/$2.50
  for 3.5 Flash-Lite. The cheapest listed stable text Flash-Lite is therefore
  2.5; free requests cost zero. GEMINI_MODEL remains configurable, with preview
  identifiers and URL/path injection rejected.
- [Regions](https://ai.google.dev/gemini-api/docs/available-regions): Uzbekistan
  is listed. Actual execution location also matters; do not assume a hosted
  runner is in the same region as its owner.
- [Terms](https://ai.google.dev/gemini-api/terms), effective 2026-03-23:
  free content can improve Google products and can be read by human reviewers.
  Only Paid Services may make API clients available to EEA/CH/UK users. Age and
  geographic restrictions also apply.
- [Limits](https://ai.google.dev/gemini-api/docs/rate-limits): project RPM/TPM/RPD
  can vary. Offscroll's local 50/day cap does not promise 50 provider successes.
- [Structured output](https://ai.google.dev/gemini-api/docs/structured-output)
  and [generateContent](https://ai.google.dev/api/generate-content): JSON schema
  requests still need application validation.

## Decision

Use an httpx Gemini adapter behind Summarizer. No dependency was added. Activate
only with nonblank GEMINI_API_KEY; otherwise use TemplateSummarizer. Keys travel
in a header, never query strings or logs. No billing API, grounding, tools, visitor
calls, retries, scraped bodies, authors, usernames, statistics or YouTube inputs.
"Batch" here means the local sequential build job, not Google's paid Batch API.

Public metadata can contain personal data. Require review of the exact title,
source, domain and optional source-provided description/extract; approval is a
SHA-256 hash in `config/summary_public_inputs.json`, empty by default. Changed
text needs renewed review. Obvious contact/credential patterns are additionally
blocked. `summary-inputs` supplies a local review manifest. Human review is the
semantic privacy boundary: automation cannot prove arbitrary prose nonpersonal.
Do not approve identifying or sensitive material, even if publicly accessible.

Cache successful output by public-input/model/prompt hash before requests. Reserve
one call in the existing raw.api_quota_usage table, source=gemini, UTC day, in a
separate atomic transaction; allow exactly 50, including failed requests. Failed
build rollback cannot refund calls. All API errors, 429, refusal/truncation and
invalid JSON/schema output use templates immediately. Pydantic enforces a short
string, at most two sentences, no extra fields, contacts/control characters or
"verified". Store model, version, hash, reported tokens and zero free-tier cost.
Unknown error usage cannot be inferred. Fallback rows are labelled Source context;
actual model output is labelled AI-generated summary. Nothing claims factual proof.

## Options and fallbacks

Gemini is the accepted primary provider. Groq free tier remains the operational
fallback option, followed by templates. Per the one-provider requirement, there
is no automatic transfer to Groq or second secret reader; Gemini errors immediately
use templates. A future Groq migration must recheck its current model/free limits
and terms. This avoids sending data to a second processor unexpectedly.

## Residual risk and conservative public delivery

Offline generation does not establish an exemption from the broad EEA/CH/UK
API-client wording. Global static exports and public web routes use templates,
while locally viewed digests may include reviewed Gemini summaries. This reduced
form preserves the feature without billing or unsupported region assertions.
No geographic bypass or billing enablement is implemented. A future change needs
provider clarification or a compatible free provider, recorded in an ADR.

The owner must keep project billing disabled; an API key alone cannot prove its
billing tier. No live Gemini request was made during AI development: unit/fake
provider and database tests validate behavior; account/credential setup is owner
work. Generated prose can still be inaccurate despite valid schema and prompts.
