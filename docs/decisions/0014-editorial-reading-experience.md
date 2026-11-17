# 0014: An editorial reading experience with browser-local controls

Status: accepted
Date: 2026-11-17 (Asia/Tashkent)

## Context and options

The owner wants a portfolio-quality product they will use on a phone, and selected
calm editorial styling. The functioning M6 pipeline needs a useful reading surface,
not a replacement backend. Options: a client framework; a hosted site builder; or
progressive enhancement of the existing Jinja/static delivery. Choose the latter:
real content is available immediately, links work without JavaScript, and the same
interface serves both static export and FastAPI without a second data model.

## Decision

Use warm paper, forest green, serif headlines, source-specific editorial sections,
clear typography, responsive navigation and a finite ending. Add light/dark choice,
explicit Save/Mark read controls, a saved-only view and progress. Browser storage
contains item identifiers/links, booleans and timestamps, never copied video metadata
or article text. No interaction is sent to a server. Previously chosen state is
pruned on the next visit after 30 days; a clear-data control removes it. Blocked
storage degrades to per-visit state. Saves show only selections in the current
edition; no promise of a cross-device or permanent archive.

Date the page from the saved digest's generation timestamp, not the export or HTTP
request time. Show a warning after four days. An app manifest and original local
icons support home-screen shortcuts. No service worker: deliberate online loading
avoids retaining stale editions or video metadata in an offline cache. System fonts
avoid font-CDN requests and keep the page light. Source ranking stays unchanged.

### YouTube player addendum to ADRs 0008/0010

Public JSON and HTML still store only video IDs/links, never titles/thumbnails or
scores. After an explicit "Load player" choice, create the official privacy-enhanced
YouTube iframe. YouTube supplies its own current metadata and controls. No autoplay,
media download, scraped content, cover over player controls, or custom category.
Keep the player viewport at least 200×200, clear branding, direct YouTube fallback,
and strict-origin-when-cross-origin referrer policy for client identity. The first
page load makes no third-party request. Loading a player shares the visitor's IP
and site origin with Google; privacy-enhanced does not mean anonymous or no storage.
Explain this beside the controls and in the privacy section. Local file:// previews
use the direct links; embeds need a served HTTP(S) origin.

## Validation and dependencies

- @playwright/test (development only): real desktop/mobile interaction and layout
  regression tests; outside requests are blocked and the player is mocked.
- @axe-core/playwright (development only): WCAG A/AA automated accessibility checks
  in light/dark mode, supplementing keyboard and visual review.
- Prettier (development only): readable, consistently checked JavaScript/CSS.

No frontend runtime dependency or build framework. Existing Python checks remain;
a new browser CI job adds checks rather than changing thresholds to hide failures.
Screenshots in docs/images are actual renders of the real local digest, not mockups.

## Residual risk and fallback

Third-party playback may fail because of regional restrictions, removed videos,
network policy or YouTube availability; the original link remains. Browser-local
preferences do not sync and can be cleared by the browser. Automated accessibility
checks are not a complete assistive-technology audit. With JavaScript unavailable,
all source sections, ordinary links, policy information and the ending still work.

## Official sources verified 2026-11-17

- https://developers.google.com/youtube/player_parameters — minimum dimensions and
  official iframe mechanism; retain standard controls.
- https://developers.google.com/youtube/terms/required-minimum-functionality —
  Referer-based client identity and recommended referrer policy.
- https://support.google.com/youtube/answer/171780 — privacy-enhanced domain and
  its limitations; the policies still apply.
- https://developers.google.com/youtube/terms/developer-policies-guide — privacy,
  clear attribution and compliance-audit fallback. ADR 0008 uncertainty remains.
- https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest/Reference/start_url
  — start URL/scope; keep static project-site paths relative.
- https://playwright.dev/docs/intro — supported browser/mobile test tooling.
