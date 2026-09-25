#!/usr/bin/env bash
# Apply repository hardening for py-atmos (rulesets + settings).
# Requires: gh auth with repo admin scopes.
set -euo pipefail

OWNER="${OWNER:-marpi82}"
REPO="${REPO:-py-atmos}"
API="repos/${OWNER}/${REPO}"

need_auth() {
  if ! gh api user --jq .login >/dev/null 2>&1; then
    echo "gh is not authenticated. Run: gh auth login -h github.com" >&2
    exit 1
  fi
}

patch_repo() {
  echo "Updating repository settings..."
  gh api -X PATCH "${API}" --input - <<'EOF'
{
  "has_wiki": false,
  "has_projects": true,
  "has_issues": true,
  "allow_squash_merge": true,
  "allow_merge_commit": true,
  "allow_rebase_merge": true,
  "allow_auto_merge": true,
  "delete_branch_on_merge": true,
  "allow_update_branch": true,
  "squash_merge_commit_title": "PR_TITLE",
  "squash_merge_commit_message": "COMMIT_MESSAGES"
}
EOF
}

enable_security() {
  echo "Enabling vulnerability alerts and automated security fixes..."
  gh api -X PUT "${API}/vulnerability-alerts" --silent || true
  gh api -X PUT "${API}/automated-security-fixes" --silent || true
  # Secret scanning / push protection (available on public repos).
  gh api -X PUT "${API}/secret-scanning/alerts" --silent 2>/dev/null || true
  gh api -X PATCH "${API}" --input - <<'EOF' || true
{
  "security_and_analysis": {
    "secret_scanning": { "status": "enabled" },
    "secret_scanning_push_protection": { "status": "enabled" },
    "dependabot_security_updates": { "status": "enabled" }
  }
}
EOF
}

create_or_replace_ruleset() {
  local name="$1"
  local body="$2"
  local existing_id
  existing_id="$(gh api "${API}/rulesets" --jq ".[] | select(.name==\"${name}\") | .id" | head -n1 || true)"
  # Solo-maintainer Admin role can always bypass (create tags, land first PRs).
  body="$(python3 -c '
import json,sys
r=json.loads(sys.argv[1])
r["bypass_actors"]=[{"actor_id":5,"actor_type":"RepositoryRole","bypass_mode":"always"}]
print(json.dumps(r))
' "${body}")"
  if [[ -n "${existing_id}" ]]; then
    echo "Updating ruleset ${name} (${existing_id})..."
    gh api -X PUT "${API}/rulesets/${existing_id}" --input - <<<"${body}"
  else
    echo "Creating ruleset ${name}..."
    gh api -X POST "${API}/rulesets" --input - <<<"${body}"
  fi
}

ruleset_main() {
  # No required status checks yet — add them when CI workflows exist.
  cat <<'EOF'
{
  "name": "protect-main",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/main"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": true,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true,
        "allowed_merge_methods": ["merge", "squash", "rebase"]
      }
    },
    { "type": "non_fast_forward" },
    { "type": "deletion" }
  ]
}
EOF
}

ruleset_release() {
  cat <<'EOF'
{
  "name": "protect-release/**",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/release/**"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false,
        "allowed_merge_methods": ["merge", "squash", "rebase"]
      }
    },
    { "type": "non_fast_forward" },
    { "type": "deletion" }
  ]
}
EOF
}

ruleset_tags() {
  # CalVer patterns for YYYY.M / YYYY.M.N and aN/bN/rcN pre-releases.
  cat <<'EOF'
{
  "name": "protect-tags",
  "target": "tag",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": [
        "refs/tags/20[0-9][0-9].[0-1]?[0-9]",
        "refs/tags/20[0-9][0-9].[0-1]?[0-9].[0-3]?[0-9]",
        "refs/tags/20[0-9][0-9](a|b|rc)[0-9]+",
        "refs/tags/20[0-9][0-9].[0-1]?[0-9](a|b|rc)[0-9]+",
        "refs/tags/20[0-9][0-9].[0-1]?[0-9].[0-3]?[0-9](a|b|rc)[0-9]+"
      ],
      "exclude": []
    }
  },
  "rules": [
    { "type": "creation" },
    { "type": "deletion" },
    { "type": "non_fast_forward" }
  ]
}
EOF
}

main() {
  need_auth
  patch_repo
  enable_security
  create_or_replace_ruleset "protect-main" "$(ruleset_main)"
  create_or_replace_ruleset "protect-release/**" "$(ruleset_release)"
  create_or_replace_ruleset "protect-tags" "$(ruleset_tags)"
  echo
  echo "Done. Current rulesets:"
  gh api "${API}/rulesets" --jq '.[] | {id,name,target,enforcement}'
}

main "$@"
