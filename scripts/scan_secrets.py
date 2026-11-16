"""No-account pattern scan of Git blobs; never read a working-tree .env or print matches."""

import argparse
import re
import subprocess

PATTERNS = {
    "google-key": rb"AIza[0-9A-Za-z_-]{35}",
    "github-token": rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})",
    "aws-access-key": rb"AKIA[0-9A-Z]{16}",
    "private-key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "provider-key": rb"sk-(?:proj-)?[A-Za-z0-9_-]{32,}",
}
CREDENTIAL_URL = re.compile(rb"postgres(?:ql)?(?:\+psycopg)?://([^\s:/]+):([^\s@]+)@")
SAFE_PASSWORDS = {
    b"ci_placeholder_password",
    b"replace_me_password",
    b"PASSWORD",
    b"password",
    b"{password}",
    b"{quoted_password}",
    b"{quote(password)}",
    b"pass",
    b"p",
    b"bad",
}


def findings(data: bytes) -> set[str]:
    result = {name for name, pattern in PATTERNS.items() if re.search(pattern, data)}
    for match in CREDENTIAL_URL.finditer(data):
        password = match.group(2)
        # Literal test/document placeholders are explicit, not a blanket file exemption.
        if password not in SAFE_PASSWORDS and not password.startswith((b"{", b"$")):
            result.add("database-password")
    return result


def git(*args: str) -> bytes:
    # All commands are fixed Git operations; paths come from Git object/index metadata.
    return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL)  # noqa: S603,S607


def scan(staged: bool = False) -> tuple[int, list[tuple[str, str]]]:
    failures = []
    objects = set()
    excluded = set()
    if staged:
        entries = git("ls-files", "--stage", "-z").split(b"\0")
        for entry in entries:
            if not entry:
                continue
            metadata, path = entry.split(b"\t", 1)
            if path.rsplit(b"/", 1)[-1].startswith(b".env") and not path.endswith(b".env.example"):
                failures.append(("index", "tracked-dotenv"))
                excluded.add(metadata.split()[1].decode())
                continue  # Do not read this file, even indirectly.
            objects.add(metadata.split()[1].decode())
    else:
        for entry in git("rev-list", "--objects", "--all").splitlines():
            parts = entry.split(b" ", 1)
            if (
                len(parts) == 2
                and parts[1].rsplit(b"/", 1)[-1].startswith(b".env")
                and not parts[1].endswith(b".env.example")
            ):
                failures.append((parts[0].decode(), "tracked-dotenv"))
                excluded.add(parts[0].decode())
                continue
            objects.add(parts[0].decode())
    blobs = 0
    for oid in sorted(objects - excluded):
        if git("cat-file", "-t", oid).strip() != b"blob":
            continue
        blobs += 1
        for rule in findings(git("cat-file", "blob", oid)):
            failures.append((oid, rule))
    return blobs, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args()
    count, failures = scan(args.staged)
    for oid, rule in failures:
        print(f"object={oid} rule={rule}")  # Never print candidate secret values or file contents.
    print(f"scanned_blobs={count} findings={len(failures)}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
