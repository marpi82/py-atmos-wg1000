# Contributing to py-atmos-wg1000

Thanks for helping improve py-atmos-wg1000.

## How to contribute

1. Open an issue describing the bug or enhancement (optional but appreciated) — use the [issue templates](https://github.com/marpi82/py-atmos-wg1000/issues/new/choose).
2. Fork the repository and create a feature branch from `main`.
3. Make your changes with tests where practical.
4. Open a pull request against `main` (the [PR template](.github/PULL_REQUEST_TEMPLATE.md) is applied automatically).

Do **not** file security issues publicly — see [SECURITY.md](SECURITY.md).

## Requirements for acceptable contributions

- **Tests**: major new functionality MUST come with tests; bug fixes should add a regression test where practical. Offline tests must pass; live gateway tests are opt-in (`@pytest.mark.needs_gateway`).
- **Style**: `ruff format` + `ruff check` clean, `mypy --strict` clean, English only in code and docs, Google-style docstrings. Run `uv run --group dev --group test poe validate` before pushing.
- **DCO**: every commit MUST be signed off (`git commit -s`) to certify the [Developer Certificate of Origin](https://developercertificate.org/).

## Development setup

```bash
uv sync --locked --group dev --group test --python 3.13
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

Useful commands:

```bash
uv run ruff check .
uv run ruff format --check
uv run mypy
uv run pytest -q
uv run --group dev poe security
```

## Coding standards

- Target Python 3.13+.
- Format and lint with **Ruff**; type-check with **mypy** (strict).
- Prefer small, focused PRs with clear commit messages.
- Never commit `.env` or live gateway credentials.

## Security reports

Do **not** open a public issue for vulnerabilities. Follow [SECURITY.md](SECURITY.md)
and email `marpi82.dev@google.com`.

## License

By contributing, you agree that your contributions are licensed under the MIT License.

## Branch protection

See [.github/branch-protection-checklist.md](.github/branch-protection-checklist.md).
