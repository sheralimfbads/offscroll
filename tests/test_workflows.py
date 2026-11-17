from pathlib import Path

import yaml


def test_schedules_and_publication_require_owner_enablement():
    pipeline = yaml.safe_load(Path(".github/workflows/pipeline.yml").read_text())
    # YAML 1.1 treats the GitHub Actions key 'on' as true.
    triggers = pipeline.get("on", pipeline.get(True))
    assert "schedule" not in triggers
    assert "workflow_dispatch" in triggers
    collect = pipeline["jobs"]["collect"]
    assert collect["if"] == "vars.ENABLE_PIPELINE == 'true'"
    assert "GEMINI_API_KEY" not in collect["env"]
    uploads = [
        step
        for step in collect["steps"]
        if step.get("uses", "").startswith("actions/upload-artifact")
    ]
    assert all(step["with"]["retention-days"] <= 7 for step in uploads)
    pages = yaml.safe_load(Path(".github/workflows/pages.yml").read_text())
    assert pages["jobs"]["build"]["if"] == "vars.ENABLE_PAGES == 'true'"
    assert pages["jobs"]["deploy"]["needs"] == "build"
    assert "GEMINI_API_KEY" not in pages["jobs"]["build"]["env"]


def test_container_context_and_compose_exclude_dotenv():
    assert ".env" in Path(".dockerignore").read_text().splitlines()
    assert "--env-file /dev/null" in Path("Makefile").read_text()
    image = Path("Dockerfile").read_text()
    assert "USER 10001:10001" in image
    compose = yaml.safe_load(Path("compose.yaml").read_text())
    assert compose["services"]["app"]["read_only"] is True
    assert compose["services"]["app"]["cap_drop"] == ["ALL"]


def test_cloud_editions_require_enablement_and_publish_only_after_health_checks():
    edition = yaml.safe_load(Path(".github/workflows/edition.yml").read_text())
    triggers = edition.get("on", edition.get(True))
    assert triggers["schedule"] == [{"cron": "17 3 * * 1,3,5"}]
    build = edition["jobs"]["build"]
    assert build["if"] == "vars.ENABLE_EDITIONS == 'true' && github.ref == 'refs/heads/main'"
    assert build["timeout-minutes"] <= 25
    assert build["env"]["YOUTUBE_RUN_LIMIT"] == "200"
    assert "secrets.DATABASE_URL" not in str(build)
    assert "GEMINI_API_KEY" not in str(build)
    commands = "\n".join(step.get("run", "") for step in build["steps"])
    assert commands.index("offscroll.cloud") < commands.index("offscroll run-all")
    assert commands.index("offscroll doctor") > commands.index("offscroll export-site")
    assert not any(step.get("continue-on-error") for step in build["steps"])
    assert edition["jobs"]["deploy"]["needs"] == "build"
    assert edition["concurrency"]["cancel-in-progress"] is False
    assert edition["permissions"] == {"contents": "read"}
