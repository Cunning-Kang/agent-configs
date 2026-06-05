#!/usr/bin/env bash
set -euo pipefail

emit_json() {
  local mode="$1"
  local reason="$2"
  local context="$3"
  local hook_event="$4"
  local permission_decision="$5"
  local tool_input_json="$6"

  jq -cn \
    --arg mode "$mode" \
    --arg reason "$reason" \
    --arg context "$context" \
    --arg hook_event "$hook_event" \
    --arg permission_decision "$permission_decision" \
    --argjson tool_input "$tool_input_json" '
      {
        hookSpecificOutput: (
          {
            hookEventName: $hook_event,
            updatedInput: $tool_input
          }
          + (if $context != "" then {additionalContext: $context} else {} end)
          + (if $permission_decision != "" then {
              permissionDecision: $permission_decision,
              permissionDecisionReason: $reason
            } else {} end)
        )
      }
      + (if $mode == "block" then {
          continue: false,
          stopReason: $reason
        } else {} end)
    '
}

parse_github_repo_from_remote() {
  local remote_url="$1"
  python - <<'PY' "$remote_url"
import re
import sys

url = sys.argv[1].strip()
patterns = [
    r'git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$',
    r'https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$',
    r'ssh://git@github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$',
]
for pattern in patterns:
    match = re.match(pattern, url)
    if match:
        print(f"{match.group('owner')}/{match.group('repo')}", end="")
        raise SystemExit(0)
raise SystemExit(1)
PY
}

main() {
  local payload tool_input_json command hook_event cwd branch upstream remote remote_url repo default_branch worktree_root
  local pr_json open_pr_count merged_pr_count closed_pr_count allow_context repo_and_default

  payload="$(cat)"
  tool_input_json="$(printf '%s' "$payload" | jq -c '.tool_input // {}')"
  command="$(printf '%s' "$payload" | jq -r '.tool_input.command // ""')"
  hook_event="$(printf '%s' "$payload" | jq -r '.hook_event_name // "PreToolUse"')"

  if [[ ! "$command" =~ ^[[:space:]]*git[[:space:]]+push([[:space:]]|$) ]] && [[ ! "$command" =~ ^[[:space:]]*gh[[:space:]]+pr[[:space:]]+create([[:space:]]|$) ]]; then
    emit_json "allow" "" "" "$hook_event" "" "$tool_input_json"
    exit 0
  fi

  cwd="$(printf '%s' "$payload" | jq -r '.tool_input.cwd // empty')"
  if [[ -z "$cwd" || ! -d "$cwd" ]]; then
    cwd="$PWD"
  fi

  if ! git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    emit_json "block" "Push/PR preflight failed: target cwd is not inside a git worktree." "" "$hook_event" "deny" "$tool_input_json"
    exit 0
  fi

  worktree_root="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || true)"
  branch="$(git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  if [[ -z "$branch" || "$branch" == "HEAD" ]]; then
    emit_json "block" "Push/PR preflight failed: could not determine the current branch in the target worktree." "" "$hook_event" "deny" "$tool_input_json"
    exit 0
  fi

  if ! upstream="$(git -C "$cwd" rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null)"; then
    upstream=""
  fi

  if [[ -n "$upstream" ]]; then
    remote="${upstream%%/*}"
  elif git -C "$cwd" remote get-url origin >/dev/null 2>&1; then
    remote="origin"
  else
    remote="$(git -C "$cwd" remote 2>/dev/null | head -n 1 || true)"
  fi

  if [[ -z "$remote" ]]; then
    emit_json "block" "Push/PR preflight failed: no git remote is configured for the target worktree." "" "$hook_event" "deny" "$tool_input_json"
    exit 0
  fi

  remote_url="$(git -C "$cwd" remote get-url "$remote" 2>/dev/null || true)"
  if [[ -z "$remote_url" ]]; then
    emit_json "block" "Push/PR preflight failed: could not resolve the configured remote URL." "" "$hook_event" "deny" "$tool_input_json"
    exit 0
  fi

  repo=""
  default_branch=""
  if command -v gh >/dev/null 2>&1; then
    if repo_and_default="$(cd "$cwd" && gh repo view --json nameWithOwner,defaultBranchRef --jq '[.nameWithOwner, .defaultBranchRef.name] | @tsv' 2>/dev/null)"; then
      repo="${repo_and_default%%$'\t'*}"
      default_branch="${repo_and_default#*$'\t'}"
    fi
  fi

  if [[ -z "$repo" ]]; then
    if ! repo="$(parse_github_repo_from_remote "$remote_url")"; then
      emit_json "block" "Push/PR preflight failed: could not resolve a GitHub owner/repo from the target remote." "" "$hook_event" "deny" "$tool_input_json"
      exit 0
    fi
  fi

  if [[ -z "$default_branch" ]]; then
    default_branch="$(git -C "$cwd" symbolic-ref --short "refs/remotes/${remote}/HEAD" 2>/dev/null | sed "s#^${remote}/##" || true)"
  fi
  if [[ -z "$default_branch" ]]; then
    default_branch="main"
  fi

  if ! command -v gh >/dev/null 2>&1; then
    emit_json "block" "Push/PR preflight failed: gh is required for PR-state checks but is not available." "" "$hook_event" "deny" "$tool_input_json"
    exit 0
  fi

  if ! pr_json="$(gh pr list -R "$repo" --state all --head "$branch" --json number,state,headRefName,mergedAt,isDraft 2>/dev/null)"; then
    emit_json "block" "Push/PR preflight failed: could not query PR state for ${repo}." "" "$hook_event" "deny" "$tool_input_json"
    exit 0
  fi

  open_pr_count="$(printf '%s' "$pr_json" | jq '[.[] | select(.state == "OPEN")] | length')"
  merged_pr_count="$(printf '%s' "$pr_json" | jq '[.[] | select(.state == "MERGED")] | length')"
  closed_pr_count="$(printf '%s' "$pr_json" | jq '[.[] | select(.state == "CLOSED")] | length')"

  allow_context="Push/PR preflight passed in ${repo} at ${worktree_root:-$cwd}. Branch=${branch}; default=${default_branch}; upstream=${upstream:-none}; open_prs=${open_pr_count}; merged_prs=${merged_pr_count}; closed_prs=${closed_pr_count}."

  if [[ "$command" =~ ^[[:space:]]*gh[[:space:]]+pr[[:space:]]+create([[:space:]]|$) ]]; then
    if [[ "$branch" == "$default_branch" ]]; then
      emit_json "block" "PR preflight failed: refusing to create a PR from the default branch (${default_branch}). Create a feature branch first." "$allow_context" "$hook_event" "deny" "$tool_input_json"
      exit 0
    fi

    if [[ -z "$upstream" ]]; then
      emit_json "block" "PR preflight failed: the current branch has no upstream. Push the branch first so PR creation targets the intended remote branch." "$allow_context" "$hook_event" "deny" "$tool_input_json"
      exit 0
    fi

    if [[ "$open_pr_count" != "0" ]]; then
      emit_json "block" "PR preflight failed: this branch already has an open PR." "$allow_context" "$hook_event" "deny" "$tool_input_json"
      exit 0
    fi

    if [[ "$merged_pr_count" != "0" || "$closed_pr_count" != "0" ]]; then
      emit_json "block" "PR preflight failed: this branch already has a merged or closed PR. Reuse needs explicit review." "$allow_context" "$hook_event" "deny" "$tool_input_json"
      exit 0
    fi
  fi

  if [[ "$command" =~ ^[[:space:]]*git[[:space:]]+push([[:space:]]|$) ]]; then
    if [[ "$branch" != "$default_branch" && ( "$merged_pr_count" != "0" || "$closed_pr_count" != "0" ) ]]; then
      emit_json "block" "Push preflight failed: this non-default branch already has a merged or closed PR. Reuse needs explicit review." "$allow_context" "$hook_event" "deny" "$tool_input_json"
      exit 0
    fi
  fi

  emit_json "allow" "Push/PR preflight passed." "$allow_context" "$hook_event" "allow" "$tool_input_json"
}

main "$@"
