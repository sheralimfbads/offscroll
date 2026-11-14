# Working on Offscroll

## Goal and stack

- Build a weekly digest that collects, ranks, and summarizes items from a few sources.
- Use Python 3.11+, httpx, and pytest. PostgreSQL and FastAPI are planned for later.
- Keep code straightforward and explainable for a beginner learning backend and data engineering.

## Workflow

- Inside the current milestone, proceed without waiting for approval: finish the
  whole task, run `make check`, and report a short summary.
- Stop and ask only if a dependency is needed that the task did not list, a DB
  schema change goes beyond the task, secrets or CI secrets are involved, or
  requirements conflict.
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
- Never read `.env` during AI work, including indirectly through commands or scripts.

## Data and compliance

- Every source connector must state its retention rule.
- YouTube: stored API data must be refreshed or deleted within 30 days.
- Link out to originals instead of copying article text or images.
- Never download videos, scrape YouTube, or store audiovisual files.
- Never present unchecked claims as verified.
