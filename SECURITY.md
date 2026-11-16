# Security

Never put credentials in issues, chat, screenshots, URLs, commits or `.env` files
read by automation. Offscroll reads exported environment variables only; secrets
are masked in settings and sent to providers in headers. Keep shell tracing off.

Report suspected vulnerabilities privately through the repository's GitHub
Security advisory mechanism if the owner has enabled it; otherwise contact the
owner privately before publishing exploit details. Do not include keys or dumps.
The owner must configure a contact/reporting channel before public launch.

Run `make check`, `make test-integration` against a disposable database, and
`make secrets`. The no-account scan checks reachable history for common Google,
GitHub, AWS, provider-token, private-key and PostgreSQL-password patterns. Explicit
synthetic test placeholders are exempt; findings print object IDs/rules, never
matched values. One immutable local tool-checkpoint blob
(`c44a14af25b2e300a1519d2ae72bdcd6246e9669`, the original scanner unit-test fixture)
has an exact object/rule exception for its deliberate synthetic database URL.
That fixture still must trigger the detector in unit tests; other blobs receive
no such exception. It is a pattern scan, not proof against all credential formats.

Untrusted source text is validated/escaped and never treated as model instructions.
Model input needs exact human review for personal data. Output validation cannot
establish truth. Public exports exclude model prose and YouTube API metadata.
Visitor routes are read-only; use a read-only DB user if exposing FastAPI. Static
hosting has the smallest attack surface. The disabled scheduler needs operational
monitoring, source purge and seven-day backup expiry before launch.

If a credential leaks: revoke it, assess exposure, then coordinate replacement and
history cleanup. Never paste it into a diagnostic command. Accounts, rotations,
secret configuration, production restores and destructive cleanup are owner tasks.
