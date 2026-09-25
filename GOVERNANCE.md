# Governance

## Model

py-atmos is a single-maintainer project: the owner (@marpi82) makes all final decisions on direction, releases, and dispute resolution (benevolent-dictator model). This may evolve if regular co-maintainers join.

## Roles and responsibilities

| Role | Who | Responsibilities |
| --- | --- | --- |
| Maintainer / owner | @marpi82 | Reviews and merges PRs, triages issues, cuts releases, owns security response (see `SECURITY.md`), manages repository settings and access |
| Contributors | anyone | Open issues and PRs, follow `CONTRIBUTING.md` and the code of conduct |

Only the maintainer has access to sensitive resources (repository settings, PyPI trusted publishing, security advisories).

## Access changes

Escalated permissions (e.g. collaborator with write access) are granted only after a track record of reviewed contributions, and are reviewed when activity changes.

## Continuity

To keep the project viable if the maintainer becomes unavailable:

- A GitHub account successor is designated (GitHub Settings → Succession).
- PyPI publishing uses trusted publishing (OIDC) from this repository's release workflow.
- All project state lives in this public repository and can be forked under the MIT license.

## Decisions

- Day-to-day: decided in GitHub issues/PR discussions.
- Breaking changes to the public API (`pyatmos_wg1000.__all__`) require an explicit maintainer decision recorded in the PR.
