---
name: code-review
description: Review checklist for py-atmos pull requests. Use when reviewing PRs to verify WebSocket protocol correctness, config vs runtime split, async safety, mypy strict compliance, public API stability, tests, and security.
---

# Code Review — py-atmos

Review procedure for pull requests to this library. Work through every section; only comment on real issues, with file/line references and a concrete suggested fix.

## 1. Correctness — protocol and data flow

- [ ] Client frames still carry the 32-byte session id; CRC check unchanged.
- [ ] Config-time language loading is not forced onto the runtime feed path.
- [ ] Feed still polls; no invented push subscription.
- [ ] Hello precedes parameter reads when required by the gateway.

## 2. Async & concurrency

- [ ] No blocking calls in the event loop.
- [ ] Poll / background tasks catch and log failures; suppress only expected cancellation.

## 3. Typing & style gates

- [ ] mypy `--strict`-clean; new `Any`/`cast`/`type: ignore` justified.
- [ ] Ruff: line length 130, Google docstrings on new public objects.
- [ ] Pydantic v2 idioms only.
- [ ] English-only code, comments, docstrings.

## 4. Public API & versioning

- [ ] `pyatmos_wg1000.__all__` unchanged, or the breaking change is explicit in the PR.
- [ ] No version string edited in `pyproject.toml` (hatch-vcs/CalVer from git tags).
- [ ] New dependencies justified and added via uv.

## 5. Error handling

- [ ] Protocol errors surface as `ProtocolError` / `AtmosError`.
- [ ] No broad `except Exception` without logging.

## 6. Tests

- [ ] New behavior covered; suite passes offline.
- [ ] Live gateway tests marked `@pytest.mark.needs_gateway`.
- [ ] Coverage gate (80%) not weakened.

## 7. Security & secrets

- [ ] No credentials or `.env` contents in code, tests, fixtures, or logs.
- [ ] Login payloads / passwords never logged at info/debug without redaction.

## 8. Docs

- [ ] Public behavior changes reflected in `docs/` (Sphinx `-W`).
- [ ] README examples still valid if the touched surface is covered there.

## How to report

- One comment per issue. Prioritize blockers (protocol break, data loss, crash), then majors (CI gate, typing, missing tests), then minors (style, docs).
- Prefer the smallest change that fits existing patterns.
