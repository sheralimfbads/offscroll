# Owner-only completion and launch steps

Local implementation is complete through M6; PROGRESS.md is the evidence ledger.
No branch/tag was pushed, no account/billing/secret was configured, and no live
site or new remote CI result is claimed. Do these steps in order. Do not paste
credentials into chat or commands recorded in history.

## 1. Review and merge with merge commits

Review the local diffs/ADRs and run the checks against a disposable test database.
Then, from this repository (GitHub CLI authenticated by the owner):

```bash
git status --short --branch
git log --oneline main..m6-youtube-fix
git push origin m4-ranking m4-done
gh pr create --base main --head m4-ranking --title "Add isolated digest ranking and reviewed Gemini summaries" --body "Implements M4 source lanes, retention-safe archives, deterministic summaries and an optional reviewed Gemini adapter. Local validation and policy decisions are recorded in docs/PROGRESS.md and ADRs 0008–0009."
gh pr checks m4-ranking --watch
gh pr merge m4-ranking --merge
git push origin m5-delivery m5-done
gh pr create --base main --head m5-delivery --title "Deliver the finite digest site and operational handoff" --body "Adds static and read-only web delivery, filtered backups, disabled automation and portfolio documentation. Local checks, restore and fresh-clone evidence are in docs/PROGRESS.md. Accounts, secrets and publication remain owner actions."
gh pr checks m5-delivery --watch
gh pr merge m5-delivery --merge
git push origin m6-youtube-fix m6-done
gh pr create --base main --head m6-youtube-fix --title "Repair YouTube exports and harden pipeline diagnostics" --body "Adds export provenance, lane funnels, explicit empty states, safe failures and doctor. A bounded Wikipedia discovery fallback preserves complete article metrics. Live three-source collection, four-video export and green checks are recorded in docs/INCIDENT-youtube.md."
gh pr checks m6-youtube-fix --watch
gh pr merge m6-youtube-fix --merge
```

Use **merge commits**, not squash or rebase merges, so M5 retains the M4 ancestry
and milestone tags remain meaningful. Merge M4, then M5, then M6; each starts from
the preceding milestone tip. If a check fails, fix it before merging. Do not
force-push. After all three:

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

## M7 launch: recommended path (supersedes sections 3–5 for this release)

The release candidate adds the editorial mobile UI and a disposable-database
edition workflow. It needs **only the existing YouTube key**, not a hosted database
account or DATABASE_URL secret. Standard public-repository Actions and GitHub Pages
are the free-first target; no payment/card/billing change is part of this release.

After reviewing the real screenshots, authorize or perform the following once:

1. Push M4–M7 branches/tags and merge the milestone PRs in order with merge commits,
   requiring green checks. M7's branch is m7-product-launch. No force push.
2. Set main as default branch (the connected repository currently reports
   m1-postgres-infrastructure), and select Actions as Pages source.
3. Store the existing YOUTUBE_API_KEY as the repository secret using hidden input
   or a memory-only stdin transfer. Never paste it in chat or an argument.
4. Enable ENABLE_EDITIONS only, dispatch edition.yml, verify build/doctor/deploy,
   and open the returned HTTPS URL on the phone. The cadence is Mon/Wed/Fri 08:17
   Asia/Tashkent. The earlier ENABLE_PIPELINE and ENABLE_PAGES paths stay off.

```bash
git push origin m7-product-launch
gh pr create --base main --head m7-product-launch --title "Launch Offscroll's editorial reading experience" --body "Adds responsive source sections, local reading controls, consent-based official video players and a checked free-first recurring Pages workflow. Validation and trade-offs are recorded in PROGRESS.md and ADRs 0014–0015."
gh pr checks m7-product-launch --watch
gh pr merge m7-product-launch --merge
gh repo edit sheralimfbads/offscroll --default-branch main
```

Do not run these commands before the earlier M4/M5/M6 merges. Use the GitHub Pages Settings screen for selecting Actions. Then:

```bash
gh secret set YOUTUBE_API_KEY
gh variable set ENABLE_EDITIONS --body true
gh workflow run edition.yml --ref main
gh run list --workflow edition.yml --limit 5
```

Read the YouTube policy links before public launch. License selection remains an
owner decision. Browser screenshots and automated accessibility checks are now
included; still inspect the published player and the phone's Add to Home Screen
experience. Cloud CI, the actual deployment URL and remote execution must be
recorded after they happen; local rehearsal is not a deployment claim.
