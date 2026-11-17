"""Rehearse against a disposable Postgres container; never use the owner's DB.

Default: migration + integration tests. --live: real API collection/build/doctor
with an exported YOUTUBE_API_KEY; output stays in build/cloud-rehearsal/site.
"""

import argparse
import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def command(args: list[str], env: dict[str, str], *, show: bool = True) -> str:
    # Fixed internal argv, no shell. Credentials are only passed in child environment.
    result = subprocess.run(  # noqa: S603
        args, cwd=ROOT, env=env, capture_output=True, text=True, timeout=900
    )
    output = result.stdout + result.stderr
    key = env.get("YOUTUBE_API_KEY")
    if key:
        output = output.replace(key, "[REDACTED]")
    if show:
        print(output, flush=True)
    if result.returncode:
        raise RuntimeError("Rehearsal command failed; see safe output above.")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    env = dict(os.environ)
    env.pop("GEMINI_API_KEY", None)
    if args.live and not env.get("YOUTUBE_API_KEY", "").strip():
        print("Export YOUTUBE_API_KEY for the live rehearsal.")
        return 1
    if not args.live:
        env.pop("YOUTUBE_API_KEY", None)
    name = "offscroll-rehearsal-" + uuid4().hex[:12]
    try:
        command(
            [
                "docker",
                "run",
                "--detach",
                "--rm",
                "--name",
                name,
                "--publish",
                "127.0.0.1::5432",
                "--tmpfs",
                "/var/lib/postgresql",
                "--env",
                "POSTGRES_USER=offscroll_ci",
                "--env",
                "POSTGRES_DB=offscroll_ci",
                "--env",
                "POSTGRES_PASSWORD=ci_placeholder_password",
                "postgres:18.7-bookworm",
            ],
            env,
            show=False,
        )
        port = command(["docker", "port", name, "5432/tcp"], env, show=False).rsplit(":", 1)[1]
        env["DATABASE_URL"] = (
            "postgresql+psycopg://offscroll_ci:ci_placeholder_password@127.0.0.1:"
            + port
            + "/offscroll_ci"
        )
        env.pop("PGSSLMODE", None)
        for _attempt in range(30):
            try:
                command(
                    ["docker", "exec", name, "pg_isready", "-U", "offscroll_ci"], env, show=False
                )
                break
            except RuntimeError:
                time.sleep(1)
        else:
            raise RuntimeError("Disposable database did not become ready.")
        command(["make", "migrate"], env)
        if args.live:
            env["OFFSCROLL_SOURCES"] = "hackernews,wikipedia,youtube"
            env["YOUTUBE_RUN_LIMIT"] = "200"
            output = "build/cloud-rehearsal/site"
            for arguments in (
                ["run-all"],
                ["build-digest"],
                ["export-site", "--output", output],
                ["doctor", "--site", output],
            ):
                command([".venv/bin/offscroll", *arguments], env)
        else:
            command(["make", "test-integration"], env)
    except RuntimeError, subprocess.TimeoutExpired:
        print("rehearsal=failed; owner database untouched", flush=True)
        return 1
    finally:
        command(["docker", "rm", "--force", name], env, show=False)
        print("Disposable PostgreSQL removed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
