"""Conservative run-history budget for disposable GitHub edition builds."""

import os
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

RUN_BUDGET = 200
MAX_DAILY_RUNS = 30


class CloudBudgetError(Exception):
    """Safe failure with no provider message, URL, token or response body."""


class CloudRun(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    id: int = Field(gt=0, strict=True)
    run_attempt: int = Field(ge=1, strict=True)
    created_at: datetime


class CloudRuns(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    total_count: int = Field(ge=1, le=MAX_DAILY_RUNS, strict=True)
    workflow_runs: list[CloudRun]


def validate_cloud_runs(payload: object, current_id: int, now: datetime) -> int:
    """Count every attempted build, including failed/cancelled builds, as 200 calls."""
    try:
        result = CloudRuns.model_validate(payload)
        runs = result.workflow_runs
        if len(runs) != result.total_count or len({run.id for run in runs}) != len(runs):
            raise CloudBudgetError("Incomplete workflow history; collection not started.")
        current = next((run for run in runs if run.id == current_id), None)
        if current is None or current.run_attempt != 1:
            raise CloudBudgetError("Start a new workflow dispatch instead of rerunning a job.")
        age = now - current.created_at
        if not timedelta(0) <= age <= timedelta(minutes=20):
            raise CloudBudgetError("Workflow waited too long; start a new dispatch.")
        reserved = sum(run.run_attempt for run in runs) * RUN_BUDGET
        if reserved > MAX_DAILY_RUNS * RUN_BUDGET:
            raise CloudBudgetError("Cloud daily request budget exhausted; try another day.")
        return reserved
    except ValidationError, TypeError, ValueError, OverflowError:
        raise CloudBudgetError("Invalid workflow history; collection not started.") from None


def cloud_budget(client: httpx.Client, *, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    # Include prior-day builds that could still be running across the quota reset.
    midnight = now.astimezone(ZoneInfo("America/Los_Angeles")).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    since = (midnight - timedelta(hours=1)).astimezone(UTC).isoformat()
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GH_TOKEN", "")
    if repo != "sheralimfbads/offscroll" or not token:
        raise CloudBudgetError("Cloud build requires the configured repository and workflow token.")
    try:
        run_id = int(os.environ["GITHUB_RUN_ID"])
        if os.environ.get("YOUTUBE_RUN_LIMIT") != str(RUN_BUDGET):
            raise CloudBudgetError("Cloud collection requires the 200-request per-run limit.")
        response = client.get(
            f"https://api.github.com/repos/{repo}/actions/workflows/edition.yml/runs",
            params={"created": ">=" + since, "per_page": 100},
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
                "User-Agent": "Offscroll-edition-budget",
            },
            timeout=15,
            follow_redirects=False,
        )
        if response.status_code != 200:
            raise CloudBudgetError("Workflow history unavailable; collection not started.")
        return validate_cloud_runs(response.json(), run_id, now)
    except httpx.HTTPError, KeyError, ValueError:
        raise CloudBudgetError("Cloud budget check failed; collection not started.") from None


def main() -> int:
    try:
        with httpx.Client() as client:
            reserved = cloud_budget(client)
    except CloudBudgetError as exc:
        print(str(exc))
        return 1
    print(f"cloud_reserved_request_budget={reserved} per_run_limit={RUN_BUDGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
