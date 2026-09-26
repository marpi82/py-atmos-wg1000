# Scripts

| Script | Purpose |
| --- | --- |
| `apply_github_hardening.sh` | Apply repository settings and rulesets via `gh` |
| `check_patch_coverage.sh` | Pre-push: 80% project coverage + 100% patch vs `origin/main` |
| `audit_info_names.py` | Offline Info entity-name corpus (panel + all gateway mode captions) |

Run hardening after `gh auth login`:

```bash
./scripts/apply_github_hardening.sh
```

Audit Info names before cutting a library release (no HA install needed):

```bash
uv run python scripts/audit_info_names.py --langs --strict
# or: uv run --group dev poe audit-names
```
