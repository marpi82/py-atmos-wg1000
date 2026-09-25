# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Calendar Versioning](https://calver.org/) (`YYYY.M.PATCH`).

## [Unreleased]

### Changed

- PyPI distribution name is `py-atmos-wg1000` (normalized name collision with existing `pyatmos`).

### Added

- Binary WebSocket frame codec, login, parameter read/write payloads, and ACD value decoding.
- `LanguageCatalog` for gateway language tables (`Lang.json`, `texty_brana.json`).
- `AtmosFeed` / `ValueStore` / `EventBus` for lightweight register polling.
- Repository hardening script, CODEOWNERS, GitHub templates, and CI workflows.
