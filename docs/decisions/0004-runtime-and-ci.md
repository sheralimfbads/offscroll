# 0004: Share the Python minor and keep CI independent of live services

Status: accepted
Date: 2026-11-15

## Context

Development and CI need the same Python syntax and reproducible checks without
API credentials. The new brief says CI credentials use GitHub Actions secrets;
the existing PostgreSQL service uses a deliberately public disposable test password.
On 2026-11-15 the owner delegated this specific choice to the project engineer.

## Decision

Keep Python 3.14 in `.python-version`, package metadata, and Ruff; Make verifies
the minor and CI reads the file. This is a minor pin, allowing patch updates.
The [setup-python documentation](https://github.com/actions/setup-python), checked
2026-11-15, documents `python-version-file`.

Keep the public test-only PostgreSQL password as a **narrow exception** to the
brief's secrets-only rule. It authenticates only a disposable CI database with
test fixtures, bound to runner loopback, and must never be reused for persistent
or production databases. Real API keys and production credentials still belong
in GitHub Actions secrets. Do not read `.env` during automation.
The [GitHub workflow event documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflows-in-forked-repositories),
checked 2026-11-15, explains that secrets are withheld from fork-triggered workflows
apart from `GITHUB_TOKEN`. Keeping test credentials public permits fork PR checks.
The brief is preserved verbatim; this ADR records the owner's delegated exception.

HTTP remains mocked in unit and integration tests; only integration tests connect
to PostgreSQL. `make smoke` explicitly performs one live HN page and writes to
the configured database. It is manual and absent from CI. The module entry point
uses the same argparse main function as the installed `offscroll` command.
No new dependency or CI/lint configuration change is needed.

## Alternatives considered

- Use a repository secret for the disposable password: adds setup and prevents
  ordinary fork PRs from running the same checks, without protecting valuable data.
- Run live APIs in CI: introduces quotas, credentials, unstable data, and outages
  into otherwise deterministic tests.
- Pin a Python patch: tighter reproducibility, but requires manual patch updates.

## Consequences

Contributors can run checks without real credentials. Integration tests still need
Docker/PostgreSQL. Smoke checks consume public API requests and modify their target
database, so use a disposable database when validating changes. They demonstrate
current connectivity, not complete coverage or future service availability.
The owner pushes commits/tags and obtains a fresh CI result; automation never pushes.
