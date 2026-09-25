# AGENTS.md — py-atmos

Async Python library for the local WebSocket API of an ATMOS WG1000 gateway,
designed as the data layer for a future Home Assistant integration.

## Project shape

- **Layout**: src-layout, single package `src/pyatmos_wg1000/`, tests in `tests/` (flat `test_*.py`).
- **Python**: `>=3.13.2,<3.15` (CI tests on 3.13).
- **PyPI distribution**: `py-atmos-wg1000` (import as `pyatmos_wg1000`).
- **Dependencies**: **uv** (`uv.lock` committed). Groups: `dev`, `test`, `docs`.
- **Build**: hatchling + **hatch-vcs** — version is CalVer from git tags; never hardcode a version in `pyproject.toml`.
- **Releases**: tag push → `.github/workflows/release.yml` (PyPI + GitHub Release). `main` may cut stable or `aN`/`bN`/`rcN`; `release/YYYY.M` trains may cut pre-releases only. Ruleset checklist: `.github/branch-protection-checklist.md`.

## Common commands

```bash
uv sync --group dev --group test --group docs --locked --python 3.13
uv run --group dev poe fmt
uv run --group dev poe lint
uv run --group dev poe typecheck
uv run --group dev --group test poe test
uv run --group dev --group test poe cov
uv run --group dev --group test poe validate
uv sync --locked --group dev --no-install-project && uv build --no-build-isolation
```

Pre-commit hooks exist; **pre-push** runs pytest with an **80% project** floor plus **100% patch** coverage vs `origin/main` (`scripts/check_patch_coverage.sh`). CI uploads `coverage.xml` to Codecov on PRs when `CODECOV_TOKEN` is set.

## Architecture in one paragraph

One TLS WebSocket (`wss://<host>/api/wss`) carries a binary framing protocol (version, length, optional 32-byte session id, commands, CRC). Configuration loads language tables (`Lang.json`, `texty_brana.json`) via :class:`pyatmos_wg1000.i18n.LanguageCatalog`. Runtime keeps a light poller (:class:`pyatmos_wg1000.feed.AtmosFeed`) that asks for fixed register ids and publishes :class:`pyatmos_wg1000.feed.RegisterUpdate` when a raw word changes. The gateway does not push sensor values on its own. Public surface today: `AtmosClient`, `AtmosFeed`, `LanguageCatalog`, `ValueStore`.

## Non-negotiable conventions

1. **English only** in code, comments, docstrings.
2. **mypy --strict** must pass (pydantic plugin enabled). No `Any`, no `# type: ignore` without justification.
3. **Ruff** (`line-length = 130`, rules `E,F,W,I,D,UP,RUF,SIM,B,S`, Google-style docstrings) must pass; run `poe fix` before committing.
4. **Async-first**: never block the event loop; `asyncio.to_thread()` for sync work; long-lived tasks must not die silently (`LOG.exception`).
5. **Pydantic v2** for DTOs (`ConfigDict`, `Field(...)`).
6. **Public API** is `pyatmos_wg1000.__all__`. Breaking it affects the future HA integration — call it out in PRs.
7. **Logging**: stdlib `logging.getLogger(__name__)`; library root attaches a `NullHandler` — never configure logging in library modules.
8. **Secrets**: never commit `.env`, gateway passwords, or live dumps of private session material.

## Testing

- pytest with `asyncio_mode = "auto"`.
- Live gateway tests must be marked `@pytest.mark.needs_gateway` and skip unless `PYATMOS_URL` is set.
- Protocol fixtures use captured frames (no credentials).

## Docs

Sphinx + Furo; `uv run --group docs sphinx-build -W -b html docs docs/_build/html`. Docs must describe the code as it is.

## CI gates (`.github/workflows/ci.yml`)

Parallel jobs: `secrets` (gitleaks), `dependency-review` (PRs), `security` (pip-audit advisory), `quality` (ruff + mypy), `tests`, `docs-verify`. `build` needs the blocking jobs.
