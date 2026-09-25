---
applyTo: "tests/**/*.py"
---

# Test suite rules

1. **Async**: `asyncio_mode = "auto"` — async test functions need no marker; do not add event-loop fixtures.
2. **No network by default**: tests must pass offline. Anything talking to a real WG1000 needs `@pytest.mark.needs_gateway` (skipped unless `PYATMOS_URL` is set).
3. **Captured frames**: prefer hex fixtures from offline captures; never commit live credentials or session cookies.
4. **Determinism**: no wall-clock sleeps for protocol tests; inject clocks when testing poll intervals.
5. **Coverage**: pre-push gate is `--cov-fail-under=80`; CI uploads to Codecov when configured (patch target 100%, project informational). New modules should ship with meaningful tests.
6. **Style**: same ruff/mypy rules as `src/`; fixtures in `conftest.py` stay minimal.
7. **Naming**: `tests/test_*.py`, flat layout.
