# Scripts

| Script | Purpose |
| --- | --- |
| `apply_github_hardening.sh` | Apply repository settings and rulesets via `gh` |
| `check_patch_coverage.sh` | Pre-push: 80% project coverage + 100% patch vs `origin/main` |

Run hardening after `gh auth login`:

```bash
./scripts/apply_github_hardening.sh
```
