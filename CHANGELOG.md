# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Calendar Versioning](https://calver.org/) (`YYYY.M.PATCH`).

## [Unreleased]

## [2026.9.0b6] - 2026-09-26

### Fixed

- Dashed Info captions keep the full panel head on both entities
  (``Siłow. RLA3O / RLA3Z - pozycja`` / ``… - ruch``); TextA/TextB terminal
  codes are ignored when the caption already encodes the label.
- Mixed number/text dual values without a dual caption use the caption for the
  numeric side and the raw token for text (e.g. ``Średnia temp. zewnętrz.`` +
  ``Tryb letni``).
- ``Auto(comfort)`` splits without requiring a space; outer/inner become two
  named mode entities.

## [2026.9.0b5] - 2026-09-26

### Fixed

- `part_names`: qualify abbreviated caption halves (e.g. bare ``wymag.``) and parse
  ``A / B - roleA / roleB`` valve captions into readable dual names.

## [2026.9.0b4] - 2026-09-26

### Added

- `protocol/info_value.py`: split/classify Info display strings (slash and parenthetical pairs, units, `---` missing, ON/OFF, open/stop/close).
- `encode_packed_setpoints`, `decode_circuit_general` / `decode_circuit_regime` / `encode_circuit_regime`, `regime_preset_index`.
- `AtmosClient.write_registers` for homepage `SetPrm` writes.

## [2026.9.0b3] - 2026-09-26

### Added

- PAGE_DATA Info and OwnText codecs (`protocol/data.py`), including `AC16_TEXT_INDEX` value expansion.
- `AtmosClient.fetch_info` / `fetch_own_text` and `InfoFeed` for polling the Info page dump.
- Export `DataKind` and Info helpers from `pyatmos_wg1000.protocol`.

## [2026.9.0b2] - 2026-09-25

### Fixed

- Build the TLS context in a worker thread and skip loading the system CA store when `verify_tls=False`, so Home Assistant no longer flags blocking `load_default_certs` on connect.

## [2026.9.0b1] - 2026-09-25

### Changed

- GitHub repository renamed to `marpi82/py-atmos-wg1000`.
- PyPI distribution name is `py-atmos-wg1000` (PyPI rejected `py-atmos` / `pyatmos` as too similar to the existing `pyatmos` project).
- Import package renamed to `pyatmos_wg1000` so a future RS-485 client can live as `pyatmos_rs485`.

### Added

- Binary WebSocket frame codec, login, parameter read/write payloads, and ACD value decoding.
- `LanguageCatalog` for gateway language tables (`Lang.json`, `texty_brana.json`).
- `AtmosFeed` / `ValueStore` / `EventBus` for lightweight register polling.
- Repository hardening script, CODEOWNERS, GitHub templates, and CI workflows.
