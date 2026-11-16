# 0010: Static GitHub Pages delivery with optional local FastAPI

Status: accepted
Date and source retrieval: 2026-11-16

## Context and options

The owner selected GitHub Pages as the default, delegated remaining decisions,
forbade pushes, and requested a disabled scheduler. A finite weekly page needs
neither a persistent web process nor a visitor-facing model API.

| Option | Verified free offer / limits | Payment card | Fit |
| --- | --- | --- | --- |
| GitHub Pages | GitHub Free public repositories; 1 GB site, soft 100 GB/month bandwidth, 10-minute deployment timeout | No paid plan needed for a public repository; account verification can vary | Selected; relative assets work under `/offscroll/` |
| Cloudflare Pages | Free plan, 500 builds/month; free product page advertises unlimited sites, requests and bandwidth | Product page explicitly says no credit card required | Alternative if Pages availability or limits change |

Official sources: [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages),
[limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits),
[Cloudflare product](https://www.cloudflare.com/products/pages/),
[Cloudflare limits](https://developers.cloudflare.com/pages/platform/limits/).
Neither static host runs PostgreSQL, collectors, or FastAPI. Owners can generate
locally; optional Actions collection requires a separately provisioned persistent
PostgreSQL service. No hosting or database account was created.

## Decision

Export one HTML page, JSON, local CSS and the official YouTube icon. Use relative
paths, escaped source text, safe HTTP(S) links, separate source sections and a
finite ending. No downloaded thumbnails, article images/text, scripts, tracking,
accounts or cookies. Light/dark responsive styles, semantic headings, skip link,
keyboard focus and reduced-motion friendly static content need no JS framework.

YouTube publication contains video ID/link only from day one: a static copy or
CDN cannot reliably delete cached metadata after 30 days. Richer recent metadata
remains available in the local CLI. Public web/API use this same projection.
Public summaries are templates per ADR 0009; reviewed Gemini output stays local.
No claim of safety, suitability, endorsement or factual verification is made.

Branding checked against [YouTube branding guidelines](https://developers.google.com/youtube/terms/branding-guidelines)
(page updated 2025-08-20) and the linked [official brand resources](https://www.youtube.com/howyoutubeworks/resources/brand-resources/).
The `video-youtube-red` SVG symbol's paths/colors/viewBox are reproduced unchanged
in `src/offscroll/static/youtube-logo.svg`; it appears with the YouTube name and
link. The icon is YouTube's brand asset, not an Offscroll license grant.

New runtime dependencies, each with one purpose:
- FastAPI: typed read-only routes and consistent HTTP errors.
- Uvicorn: a small ASGI server for the optional local/container app.
- Jinja2: shared autoescaped HTML templates for static and dynamic delivery.

Use a two-stage Python 3.14.5 image, user 10001, read-only app filesystem and
localhost-bound Compose port. [FastAPI Docker guidance](https://fastapi.tiangolo.com/deployment/docker/)
supports building a small application image rather than a legacy base image.
[Pages custom workflow instructions](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
were also verified on 2026-11-16 (configure-pages v5, upload-pages-artifact v4,
deploy-pages v4). No schema changes are needed in M5. Workflow schedule remains commented out and
manual execution is also guarded by ENABLE_PIPELINE. Pages publishing is a
separate, owner-triggered workflow; no automatic push or publication occurs.

## Residual risks and fallback

Links-only videos sacrifice convenient previews; templates sacrifice AI prose.
These are deliberate compliance trade-offs. Browser/accessibility visual review
and screenshots remain owner work; automated HTML/HTTP checks do not prove visual
quality. Hosting limits and API terms can change. Fall back to a downloaded local
static site or Cloudflare Pages after rechecking terms. HTTPS, repository visibility
and account configuration remain the owner's responsibility.
