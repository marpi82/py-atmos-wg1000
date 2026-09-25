# py-atmos Copilot Instructions

## Critical AI Guidelines

### Core Principles
1. **Always refer to the latest documentation** — Check `docs/` and `AGENTS.md` for current architecture and patterns
2. **100% English code** — All files, comments, docstrings must be in English
3. **Base on existing files** — Never create code blindly. When uncertain, ask instead of guessing
4. **Home Assistant focus** — This library's primary goal is HA integration. Keep config-time heavy and runtime light

### Language & Type Requirements (Python 3.13.2+)

- Protect mutable shared structures (locks/immutable/actor-style); do not rely on the GIL
- Complete type annotations; pass `mypy --strict`
- Follow PEP 621 for `pyproject.toml`
- Tooling: uv, Hatch/Hatchling, Ruff, Sphinx + Google-style docstrings

## Project Overview

**py-atmos** talks to a local ATMOS WG1000 over a binary WebSocket (`/api/wss`).

- **Config time**: download language tables, resolve labels (`LanguageCatalog`)
- **Runtime**: keep one socket, log in, poll registers (`AtmosFeed` → `ValueStore` / `EventBus`)

The gateway does **not** push temperatures. Polling is the acquisition model.

## Key modules

- `src/pyatmos_wg1000/client.py` — async WebSocket client
- `src/pyatmos_wg1000/protocol/` — frames, CRC, login, params, files, register catalog
- `src/pyatmos_wg1000/i18n.py` — language tables
- `src/pyatmos_wg1000/feed.py` — poller, store, bus

## Do not

- Commit `.env` or live credentials
- Invent a push API the device does not expose
- Soften mypy/ruff gates without maintainer approval
- Hardcode a package version in `pyproject.toml`
