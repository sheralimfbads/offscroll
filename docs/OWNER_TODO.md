# Owner-only completion and launch steps

Local implementation is complete through M5; PROGRESS.md is the evidence ledger.
No branch/tag was pushed, no account/billing/secret was configured, and no live
site or new remote CI result is claimed. Do these steps in order. Do not paste
credentials into chat or commands recorded in history.

## 1. Review and merge with merge commits

Review the local diffs/ADRs and run the checks against a disposable test database.
Then, from this repository (GitHub CLI authenticated by the owner):

```bash
git status --short --branch
git log --oneline main..m5-delivery
git push origin m4-ranking m4-done
gh pr create --base main --head m4-ranking --title "Add isolated digest ranking and reviewed Gemini summaries" --body "Implements M4 source lanes, retention-safe archives, deterministic summaries and an optional reviewed Gemini adapter. Local validation and policy decisions are recorded in docs/PROGRESS.md and ADRs 0008–0009."
gh pr checks m4-ranking --watch
gh pr merge m4-ranking --merge
git push origin m5-delivery m5-done
gh pr create --base main --head m5-delivery --title "Deliver the finite digest site and operational handoff" --body "Adds static and read-only web delivery, filtered backups, disabled automation and portfolio documentation. Local checks, restore and fresh-clone evidence are in docs/PROGRESS.md. Accounts, secrets and publication remain owner actions."
gh pr checks m5-delivery --watch
gh pr merge m5-delivery --merge
```

Use **merge commits**, not squash or rebase merges, so M5 retains the M4 ancestry
and milestone tags remain meaningful. Merge M4 first; M5 starts from the tip of
m4-ranking. If a check fails, fix it before merging. Do not force-push. After both:

```bash
git fetch origin
git switch main
git merge --ff-only origin/main
```

## 2. Credentials and policy review

- Read [YouTube developer policies guide](https://developers.google.com/youtube/terms/developer-policies-guide),
  [developer policies](https://developers.google.com/youtube/terms/developer-policies),
  and [branding](https://developers.google.com/youtube/terms/branding-guidelines).
  ADR 0008 accepts residual interpretation uncertainty; fallback is a plain
  chronological list or an optional [API Compliance Audit](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits).
- Create/configure a Google project and enable YouTube Data API v3 if needed;
  restrict its key to that API. Review the curated channel list; run all sources
  twice and inspect status/check-data before unattended operation.
- For optional local Gemini: review current models, regions and terms in ADR 0009;
  **do not enable billing**. Confirm the actual execution region is supported and
  free-tier data-use terms are acceptable. Generate an AI Studio key yourself.
  Export it using a hidden prompt, never through a tracked file. Review exact
  nonpersonal input hashes before use. No live Gemini smoke was performed by the
  agent. Groq remains a future provider migration, not an automatic fallback call.
- Do not set GEMINI_API_KEY in public workflows. Global delivery stays template-only.
- Choose a license; no LICENSE file is present. The YouTube logo remains its owner's
  brand asset. Configure a private security-reporting contact/advisories channel.

## 3. Persistence, retention and backups

The site works with local collection and static hosting; no cloud DB purchase is
required. To use Actions collection, provision a persistent PostgreSQL 18 endpoint
reachable from runners, require TLS (e.g. PGSSLMODE=require), and use a dedicated
least-privilege account. Do not expose the local development database publicly.
Keep migration/collection and read-only web credentials separate. The owner creates
accounts or selects an existing service; no payment is authorized or required here.

For Actions, supply the credentials using GitHub CLI's interactive secret input:

```bash
gh secret set DATABASE_URL
gh secret set YOUTUBE_API_KEY
```

Workflows default PGSSLMODE to require; verify the chosen remote DB supports TLS. The
application deliberately rejects URL query parameters, so TLS options belong in
libpq environment settings. Rehearse the empty-target restore in RUNBOOK.md; check
all downloaded backups expire within seven days. No YouTube API data or model prose
belongs in backups. Public-repository Actions artifacts are not a private vault;
choose a private destination/repository if access restrictions are required.

## 4. Enable collection only after validation

```bash
gh variable set ENABLE_PIPELINE --body true
gh workflow run pipeline.yml --ref main -f build_digest=true
gh run list --workflow pipeline.yml --limit 5
```

Inspect that run's status/check-data, 7-day backup artifact and exported site. Then
uncomment the `schedule` block in `.github/workflows/pipeline.yml` in a reviewed PR:
collection every six hours, build Monday 06:00 UTC (11:00 Asia/Tashkent). Merge that
PR with a merge commit. Leave the variable unset/false and comments intact until
ready. Monitor failures and purge even if collection stops. GitHub schedules can
be delayed; they are not a retention SLA. To pause without editing secrets:

```bash
gh variable set ENABLE_PIPELINE --body false
```

## 5. Publish GitHub Pages and inspect it

In repository Settings → Pages, select **GitHub Actions** as the source. Configure
the `github-pages` environment to allow only main and require owner review if
available. The public-repository GitHub Free option needs no paid plan. Review
`site/index.html` and `site/digest.json`; then:

```bash
gh variable set ENABLE_PAGES --body true
gh workflow run pages.yml --ref main
gh run list --workflow pages.yml --limit 5
```

pages.yml exports the saved digest using DATABASE_URL, uploads only site/, then
publishes with the official Pages actions. It never builds a digest or calls an
LLM. Publication stays manual. For fully local collection without a runner-accessible
DB, use the built site/ with a separately reviewed static-upload workflow or the
Cloudflare Pages direct-upload UI; do not upload the whole repository.

Check `https://sheralimfbads.github.io/offscroll/` after the workflow provides the
actual deployment URL. Inspect desktop/mobile, keyboard-only navigation, dark mode,
source links, attribution and the finite ending. Capture a real screenshot and
replace the README placeholder. Automated HTML tests do not replace this visual
check. Check there are no tracking requests, copied YouTube metadata, Gemini prose
or secrets in the public JSON. Keep the policy review/date current.
