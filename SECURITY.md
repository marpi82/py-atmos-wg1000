# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability in py-atmos, please report it privately:

- **Preferred**: [GitHub private vulnerability reporting](https://github.com/marpi82/py-atmos/security/advisories/new)
- **Alternative**: email marpi82.dev@google.com

Please do not create a public GitHub issue for security vulnerabilities.

## Coordinated Vulnerability Disclosure

- **Acknowledgement**: within 3 business days.
- **Initial assessment and severity triage**: within 14 days.
- **Fix or mitigation**: targeted within 90 days of confirmation, depending on severity and complexity.
- **Disclosure**: coordinated with the reporter; a GitHub Security Advisory is published once a fix is released (or when we mutually agree). Reporters are credited in the advisory unless they prefer otherwise.

## Supported Versions

Only the **latest release** receives security fixes; there are no backports to older versions.

## Security tooling

- **bandit**: Security linting for Python code (pre-commit + `poe security`)
- **ruff** (`S` / flake8-bandit): Fast security lint rules in the same pass as style checks
- **pip-audit**: Dependency vulnerability scanning
- **CodeQL**: Deeper static analysis in GitHub Actions
- **gitleaks**: Secret scanning in CI and pre-commit

### Resolved Security Exceptions

There are currently **no active dependency vulnerability exceptions** in this repository.

## Security Best Practices

When using py-atmos:

1. Keep dependencies updated (`uv sync --upgrade` in a controlled PR).
2. Run `uv run --group dev poe security` before releases.
3. Never commit gateway credentials. Use `.env` (gitignored) or a secret store.
4. Prefer loading the gateway device CA instead of disabling TLS verification in production.
5. Follow Home Assistant security guidelines when building the integration.

## Security Scanning

```bash
uv run --group dev poe security
```

This runs bandit and pip-audit. Ruff `S` rules run as part of `poe lint`. CodeQL runs in GitHub Actions.

## Update Schedule

Dependency updates arrive via Dependabot (Actions) and Renovate (Python). Security advisories are reviewed promptly.
