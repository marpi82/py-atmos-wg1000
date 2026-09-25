---
applyTo: "src/pyatmos/**/*.py"
---

# Library core rules (apply to all of src/pyatmos)

When reviewing or changing library code:

1. **Config vs runtime**: language tables and UI bundles belong in config-time paths (`LanguageCatalog`, file download). Runtime acquisition (`AtmosFeed`) stays light — raw register words only.
2. **No false push**: the gateway does not push temperatures. Polling is intentional; do not invent a subscription that the wire protocol does not have.
3. **Event-loop hygiene**: no blocking I/O in async code — use `asyncio.to_thread()`. Flag `time.sleep`, sync sockets, or heavy file I/O inside coroutines.
4. **Task lifecycle**: feed poll loops must catch and log exceptions (`logger.exception`), never die silently; reserve `contextlib.suppress` for expected outcomes like cancellation.
5. **Typing**: mypy strict. New `Any`, `cast()`, or `# type: ignore` need an inline justification comment.
6. **Errors**: wire/protocol failures raise `ProtocolError` / `AtmosError` — don't swallow framing errors or return bare `None` from codecs without documenting soft-fail contracts.
7. **Pydantic v2 only**: `ConfigDict`, `model_validate`, `Field(...)`. Flag v1 idioms.
8. **Logging**: `logging.getLogger(__name__)`, no `print`, no logging configuration in library modules.
9. **Public API**: changes to `__init__.py` exports are breaking — require explicit PR discussion.
10. **Docstrings**: Google style, English, on all public objects (ruff `D` rules enforce this).
11. **Secrets**: never log passwords, session pads, or full login payloads.
