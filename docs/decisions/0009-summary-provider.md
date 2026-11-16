# 0009: Choose an optional summary provider

Status: proposed; owner choice pending
Date: 2026-11-16

## Context

M4 P0 runs without an account: deterministic templates provide source context for
HN/Wikipedia. YouTube remains outside summaries. The brief requires checking two
or three providers and stopping for the owner to choose before implementing one.
This comparison covers two providers from official pages retrieved 2026-11-16;
no account was accessed, API key read, model called, or terms accepted.

## Options verified

| Option | Standard text pricing per million tokens (USD) | Free access and limits | Terms/data considerations |
| --- | --- | --- | --- |
| Google Gemini `gemini-2.5-flash-lite` | $0.10 input, $0.40 output | Pricing lists free input/output. Active RPM/TPM/RPD limits depend on the project and must be checked in AI Studio; no fixed free quota is promised here. | Unpaid inputs/outputs may be used to improve products and reviewed by people. Paid-service data is not used for product improvement. Terms include region/age restrictions; API clients serving EEA/UK/Switzerland users require paid services. |
| Groq `openai/gpt-oss-20b` | $0.075 input, $0.30 output | Published free limits: 30 RPM, 1,000 RPD, 8,000 TPM, 200,000 TPD; actual organization limits can differ. | Ordinary inference is not retained by default, with feature/reliability/abuse exceptions. Data Controls offers zero data retention. Groq's agreement and applicable model terms both apply; customer is responsible for inputs and evaluating outputs. |

Official sources (all retrieved 2026-11-16):

- Google [pricing](https://ai.google.dev/gemini-api/docs/pricing),
  [limits](https://ai.google.dev/gemini-api/docs/rate-limits), and
  [terms](https://ai.google.dev/gemini-api/terms), effective March 23, 2026.
  These URLs currently redirect to the corresponding AI Studio documentation.
- Groq [production models and pricing](https://console.groq.com/docs/models),
  [free rate limits](https://console.groq.com/docs/rate-limits),
  [data policy](https://console.groq.com/docs/your-data), and
  [services agreement](https://console.groq.com/docs/legal/services-agreement).

Illustrative calculation, not a bill or a quality benchmark: eleven summaries
with 500 input and 100 output tokens each would cost about $0.00099 on Gemini
or $0.0007425 on Groq at the listed paid text rates. Actual billable tokens,
including reasoning, retries and changed rates, can differ. Free access and
account eligibility must be confirmed by the owner; credentials stay out of chat.

## Decision

Pending. Recommend keeping templates until the owner wants AI summaries and can
choose an account/provider. If selecting an external provider now, Groq's listed
free allowance and data controls make it a reasonable first candidate; this is
an engineering preference, not a tested claim of better summary quality.

Available choices:

1. Defer P1 and close M4 with deterministic source-context templates.
2. Implement Groq with the chosen production model.
3. Implement Google Gemini with the chosen model/tier.

After an external-provider choice, implement exactly one adapter using existing
httpx (no new dependency needed), masked environment configuration, validated
JSON of at most two neutral sentences, safe template fallback, delimited untrusted
inputs, a fake-provider injection fixture, input-hash caching before requests,
usage/cost tracking, and an atomic hard daily call cap. No web tools, browsing,
scraped article body, YouTube metadata, or autonomous tool execution is allowed
in summary requests. Label actual LLM output AI-generated; do not claim it proves
anything. These provider safeguards are pending work, not implemented features.

## Alternatives considered

Multiple simultaneous providers would enlarge the implementation and testing
surface. A selected provider behind the existing Summarizer interface is enough.
Templates avoid cost, privacy transfer, and model uncertainty, but provide source
context rather than a substantive paraphrase of an article that was never fetched.

## Consequences

P0 ranking, lanes and persistence can be tested independently. M4 remains open at
this explicit provider decision until P1 is implemented or the owner defers it.
No `m4-done` tag is created before that decision. M5 does not start automatically.
