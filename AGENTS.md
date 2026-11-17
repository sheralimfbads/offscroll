# Working on Offscroll

## Goal and stack

- Build a weekly digest that collects, ranks, and summarizes items from a few sources.
- Use the Python minor in `.python-version`, httpx, pytest, and PostgreSQL.
  FastAPI provides optional read-only delivery; production uses static GitHub Pages.
- Keep code straightforward and explainable for a beginner learning backend and data engineering.

## Workflow

- Proceed through M4 and M5 without stopping between milestones. Run make check
  and make test-integration, review, update docs, commit and tag each milestone.
- Follow the owner's 2026-11-16 full-control directive in the project brief.
  Resolve design/policy ambiguity conservatively and document it. Only physical
  blockers (accounts, payment, secrets, push/merge, destructive actions, or three
  genuinely different failed attempts) stop affected work; continue the rest.
- Work on a branch named `m<N>-<topic>` and commit locally in small logical
  commits with imperative messages. Never commit secrets.
- Before reporting, review your own diff as a skeptical senior engineer and list
  the top three risks you see.
- Build small vertical slices.
- Give a one-line justification for every new dependency.
- Briefly explain trade-offs in every answer.

## Quality

- Every behavior change must have tests.
- Unit tests must never use the network.
- `make check` must pass.

## Security

- Never print, log, or commit secrets or URLs containing keys.
- Keep `.env` git-ignored.
- Never expose `.env` to AI context, logs or output. The narrow redacting-subprocess
  exception for necessary live work is recorded in the M7 owner amendment below.

## Data and compliance

- Every source connector must state its retention rule.
- YouTube: stored API data must be refreshed or deleted within 30 days.
- Link out to originals instead of copying article text or images.
- Never download videos, scrape YouTube, or store audiovisual files.
- Never present unchecked claims as verified.

Source of truth for scope and rules: docs/PROJECT_BRIEF.md

## M7 owner amendment (2026-11-17)

- Continue the product/portfolio launch: calm editorial design; Monday, Wednesday,
  Friday editions for smartphone use. Keep the existing backend and source policies.
- The owner permits using local configuration inside redacting subprocesses for
  necessary live checks; never expose its contents or credential values to the model,
  logs, screenshots, Git, or public output. Normal app settings stay env-only.
- Run the added offline browser/accessibility checks as well as Python/integration
  checks. Capture real screenshots, not fabricated product content.
- The owner approved the tested release on 2026-11-17: push M4–M7, merge with
  merge commits after green CI, set main as default, configure free GitHub Pages,
  transfer the existing YouTube key securely to Actions, and enable Mon/Wed/Fri
  08:17 Asia/Tashkent editions. This supersedes the earlier owner-only launch boundary.
  No payments, billing enablement, force pushes, or destructive production actions.
