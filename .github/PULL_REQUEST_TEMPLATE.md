## Summary

<!-- What does this PR change and why? Link related issues with "Fixes #N" / "Closes #N" when applicable. -->

## Type of change

<!-- Check all that apply. -->

- [ ] Bug fix (non-breaking)
- [ ] New feature / enhancement (non-breaking)
- [ ] Breaking change to the **public API** (`AtmosClient`, `AtmosFeed`, `LanguageCatalog`, or other symbols in `pyatmos_wg1000.__all__`)
- [ ] Docs only
- [ ] Tests / CI / tooling / chore

## Checklist

- [ ] Commits are signed off (`git commit -s`) — [DCO](https://developercertificate.org/)
- [ ] English only in code, comments, and docs; Google-style docstrings
- [ ] `uv run --group dev --group test poe validate` passes locally (fmt + lint + mypy --strict + security + tests)
- [ ] Tests added / updated where practical. Offline tests pass; live gateway remains `@pytest.mark.needs_gateway`
- [ ] Docs updated when public behavior changes (`docs/` + Sphinx `-W` clean)
- [ ] No secrets / credentials / live session dumps committed

## Test plan

```bash
uv run --group dev ruff check .
uv run --group dev poe typecheck
uv run --group dev --group test poe test
```

## Notes for reviewers

<!-- Trade-offs, protocol caveats, HA impact, follow-ups. -->
