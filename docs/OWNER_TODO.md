# Owner guide after launch

The owner authorized publication and automatic editions on November 17, 2026.
M4–M7 were pushed and merged in order through PRs 4–7 with merge commits after
successful CI. `main` is the default branch. GitHub Pages uses Actions and its
environment permits only `main`. The existing YouTube key was transferred into
the repository Actions secret without exposing its value. No billing was enabled.
See [PROGRESS.md](PROGRESS.md) for actual deployment and verification evidence.

## Read on your phone

Open [Offscroll](https://sheralimfbads.github.io/offscroll/). In Safari use Share →
Add to Home Screen; in Chrome use its menu → Add to Home screen (wording varies).
The shortcut requires internet access. There is no offline service worker.

Editions are scheduled Monday, Wednesday and Friday at **08:17 Asia/Tashkent**.
GitHub can delay scheduled jobs. Check the date shown on the page; a failed build
keeps the previous edition. Saved/read choices and theme stay in this browser,
expire after 30 days and do not sync between devices. Saved view filters the
current edition; it is not a permanent archive of previous selections.

YouTube contacts Google only after **Load player**. If a player is unavailable,
use **Open on YouTube**. Please inspect the live player and home-screen shortcut
on your own phone; automated browser checks do not replace a device check.

## Operate the scheduled editions

Only `ENABLE_EDITIONS=true` is enabled. Leave `ENABLE_PIPELINE` and `ENABLE_PAGES`
unset/false: those are alternative persistent-database workflows, not additional
steps for this deployment. No hosted database account or DATABASE_URL secret is
needed for the active disposable-database workflow. Public delivery is template-only;
do not add GEMINI_API_KEY to public workflows.

Inspect or request a fresh edition:

```bash
gh run list --repo sheralimfbads/offscroll --workflow edition.yml --limit 5
gh workflow run edition.yml --repo sheralimfbads/offscroll --ref main
```

Start a **new dispatch**, not a rerun of an old job: the quota guard deliberately
rejects reruns. Do not delete current Pacific quota-day workflow history, because
it is the conservative cross-run quota ledger. Prefer a dedicated YouTube API
project/key; other clients sharing a key are outside this ledger. Rotate the key
with hidden input, never an argument or pasted chat message:

```bash
gh secret set YOUTUBE_API_KEY --repo sheralimfbads/offscroll
```

Pause or resume editions without changing credentials:

```bash
gh variable set ENABLE_EDITIONS --repo sheralimfbads/offscroll --body false
# Resume only when the cause of a pause is resolved:
gh variable set ENABLE_EDITIONS --repo sheralimfbads/offscroll --body true
```

Enable GitHub Actions failure notifications for your account and check the edition
date occasionally. GitHub may disable scheduled workflows after 60 days of public
repository inactivity. When appropriate, re-enable the workflow in the Actions UI
or with `gh workflow enable edition.yml --repo sheralimfbads/offscroll`.

## Remaining owner decisions

- Read the [YouTube developer policies guide](https://developers.google.com/youtube/terms/developer-policies-guide),
  [developer policies](https://developers.google.com/youtube/terms/developer-policies),
  and [branding guidelines](https://developers.google.com/youtube/terms/branding-guidelines).
  ADR 0008 records interpretation uncertainty. Consider an optional
  [API Compliance Audit](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits);
  the conservative fallback is chronological videos from curated channels.
- Restrict the existing Google key to YouTube Data API v3. Review curated channels
  in `config/youtube_channels.yaml` and make changes through tested PRs.
- Choose a license; no LICENSE file has been added. The YouTube logo remains its
  owner's brand asset. Configure a private security-reporting contact if desired.
- Review Dependabot PRs individually; their existence does not authorize merging
  untested dependency upgrades. Never weaken CI to merge an upgrade.
- Optional local Gemini needs your own AI Studio key, current supported-region and
  data-use review, and approved nonpersonal input hashes. Keep billing disabled.
  No live Gemini call was made for this launch; Groq is a future adapter option.

## Future code releases

Use a topic branch, run `make check`, `make test-integration` with a disposable DB,
and `make test-browser`. Scan full history with `make secrets`. Push the branch,
create a PR targeting `main`, wait for green CI and merge with a merge commit:

```bash
git push -u origin YOUR_BRANCH
gh pr create --base main --head YOUR_BRANCH --title 'Describe the change' --body-file /tmp/offscroll-pr.md
gh pr checks YOUR_BRANCH --watch
gh pr merge YOUR_BRANCH --merge
git fetch origin
git switch main
git merge --ff-only origin/main
```

Do not force-push. M4–M7 launch merges are already complete; do not recreate them.
A code merge does not itself collect a new edition: use the next scheduled run or
an explicit fresh dispatch. Record a completed milestone tag only after checks.

For persistent local history/backups, follow [RUNBOOK.md](RUNBOOK.md). Do not expose
the laptop database publicly. A future hosted persistent DB needs a separate
review of TLS, least-privilege credentials, retention and cost. The current free
static deployment does not require it.
