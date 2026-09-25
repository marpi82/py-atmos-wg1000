---
applyTo: "src/pyatmos_wg1000/protocol/**/*.py, src/pyatmos_wg1000/i18n.py"
---

# Protocol and language-catalog rules

1. **Frame layout**: client frames include a 32-byte session id; server frames do not. CRC is reflected CRC-32 with stored complement (`zlib.crc32(frame) == 0xFFFFFFFF`).
2. **Hello first**: parameter reads on channel `WS` are only answered after Hello.
3. **Register ids**: use `hod16_id` / `Id33` helpers — do not hardcode magic numbers without a comment tying them to `PRM.js`.
4. **Temperature decode**: match the UI (`bit31` set, `bit30` clear, low half non-zero → `(raw & 0xFFFF) / 6.4 - 64` with JS-style rounding).
5. **i18n**: `USER1_LANG` is a zero-based language index; column 0 is the row id. Empty cells fall back to `ENG`. Do not invent translations.
6. **File download**: ack chunks with the gateway-assigned file id, not the UI list index.
