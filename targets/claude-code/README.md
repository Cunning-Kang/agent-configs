# Claude Code target

Runtime landing area for Claude Code. This directory is owned by Claude Code;
its contents may be rewritten by the tool at any time and are not a stable
contract. See `CONTEXT.md` at the repo root for the area role.

## Layout

| Path                       | Role                                                                                            |
| -------------------------- | ----------------------------------------------------------------------------------------------- |
| `CLAUDE.md`                | Direct behavior entrypoint loaded by Claude Code when it enters this tree.                      |
| `settings.json.template`   | Template for machine-specific settings. Copy to `settings.json` to use.                         |
| `mcp.json.template`        | Template for MCP server wiring. Copy to `mcp.json` to use.                                      |
| `agents/`                  | Runtime-native subagent definitions Claude Code loads directly.                                |
| `commands/`                | Slash-command definitions owned by Claude Code.                                                |
| `hooks/`                   | Executable hook implementations in Claude Code's hook format.                                   |
| `skills/`                  | Reserved for Claude Code-specific skill overrides. Reusable skill methodology lives in `assets/skills/`. |

## Migrated contents

This target was populated from the local Claude Code runtime per
`docs/maintenance/runtime-config-inventory.md`:

- `settings.json.template` — sanitized mirror of the real Claude Code settings
  schema (env, permissions allow/deny/ask/defaultMode, model, hooks,
  statusLine, enabledPlugins, extraKnownMarketplaces, language, sandbox,
  plansDirectory, skipDangerousModePermissionPrompt, theme, teammateMode,
  hasCompletedOnboarding). All secrets, model-routing values, sandbox policy
  entries, and absolute hook paths are placeholders.
- `mcp.json.template` — sanitized mirror of the real `codebase-memory-mcp`
  MCP wiring. The `command` value is a placeholder for the absolute path of
  the binary on the target machine.
- `agents/` — seven runtime subagent definitions (`code-implementer`,
  `code-reviewer`, `codebase-discovery`, `deployment-operator`, `mavis`,
  `task-planner`, `test-engineer`) plus the local `README.md` describing
  the agent set. Five of the seven (`code-implementer`, `codebase-discovery`,
  `deployment-operator`, `mavis`, `test-engineer`) carry only `model`,
  `effort`, `permissionMode`, and resolve on a clean clone if the runtime's
  `modelRoles` block is filled. `code-reviewer.md` and `task-planner.md`
  add a frontmatter `PreToolUse` hook command of the form
  `~/.claude/hooks/validate-agent-artifact-write/hook.mjs <agent>` — the
  bundle's own README in `hooks/validate-agent-artifact-write/README.md`
  states that the directory must be copied to
  `~/.claude/hooks/validate-agent-artifact-write/`; no auto-install. The
  audit marks those two agents **blocked** for the same reason.
- `commands/` — two slash-command definitions (`agent-plan`, `new-feature`).
  The `new-feature` body references `~/.claude/scripts/instantiate-feature.sh`
  using the `~`-relative form, which Claude Code expands at runtime; no
  absolute local paths are present.
- `hooks/` — five executable hooks plus the `validate-agent-artifact-write/`
  bundle:
  - `agent-model-override-gate.py` — uses `Path.home()` and a configurable
    `CLAUDE_AGENT_MODEL_OVERRIDE_SECRET_FILE` env var; no absolute paths.
  - `git-push-pr-preflight.sh` — operates on the tool-input `cwd`; no
    absolute paths.
  - `cbm-code-discovery-gate` — resolves the codebase-memory-mcp binary
    path from `$CODEBASE_MEMORY_MCP_BIN` (with a documented placeholder
    default). The committed copy has no hard-coded user path.
  - `cbm-session-reminder` — prints a static reminder; no path resolution
    required.
  - `validate-agent-artifact-write/` — uses `process.env.TMPDIR` or
    `os.tmpdir()`; no absolute paths.

Reusable skill methodology (`prototype`, `handoff`, `triage`, `to-prd`,
`to-issues`, `tdd`, `grill-me`, `grill-with-docs`, `caveman`, `diagnose`,
`improve-codebase-architecture`, `obsidian-cli`, `obsidian-markdown`,
`prototype`, `setup-matt-pocock-skills`, `verification-before-completion`,
`web-design-guidelines`, `write-a-skill`, `zoom-out`) lives in
`assets/skills/` at the repo root per the inventory classification
Reusable skill methodology (Agent Skills standard workflows) lives in
`assets/skills/` at the repo root per the inventory classification
("migrate to `assets/skills/` if reusable across runtimes"). The
shared standard workflow for promoting material from this target
into the shared layer is `assets/skills/promote-reusable-material.md`.
Role blueprints that mirror the runtime subagents in `agents/`
below live in `assets/agents/role-blueprints.md`; the runtime
wiring (model, permission scope, hooks, color, max turns) stays
in the per-agent frontmatter under `agents/` here.
The shared hook policies that document the lifecycle intent of
each executable hook under `hooks/` below live in
`assets/hooks/`:

- `agent-model-override.md` — `PreToolUse` (matcher: `Agent`) for `agent-model-override-gate.py`.
- `git-push-pr-preflight.md` — `PreToolUse` (matcher: `Bash`) for `git-push-pr-preflight.sh`.
- `codebase-memory-search-augment.md` — `PreToolUse` (matcher: `Grep|Glob`) for `cbm-code-discovery-gate`.
- `codebase-memory-session-reminder.md` — `SessionStart` (matcher: `startup|resume|clear|compact`) for `cbm-session-reminder`.
- `agent-artifact-write-scope.md` — `PreToolUse` (matcher: `Write`) for `validate-agent-artifact-write/hook.mjs`.

The MCP server contract that `mcp.json.template` wires is documented in
`assets/mcp-servers/codebase-memory-mcp.md`. The template only owns
the binary path; the card owns the transport, tools, and security
posture.

The two composition packs that group these shared assets for
common use cases are `assets/packs/codebase-memory-assisted-workflow.md`
and `assets/packs/agent-blueprint-distribution.md`.

This target keeps no skill content of its own; `skills/` is empty
by design until a Claude-Code-specific override is needed.

## Runnability status

Every committed file in this target is classified by the issue #12
audit. The full per-file table lives in
`docs/maintenance/runtime-runnability-audit.md`; this section is the
short version for readers who only need to know what works out of the
box.

**Bucket counts** (see the audit for per-file evidence). Counts are
per logical row in the audit; a single template file is split across
rows when different blocks of the same file have different buckets
(e.g. `settings.json.template` `statusLine` is template-only with a local-placeholder command while
`enabledPlugins` is template-only).

| Bucket            | Count | What it means here                                                    |
| ----------------- | ----: | --------------------------------------------------------------------- |
| `runnable`        |     7 | Works on a clean clone. The pure-documentation row (`README.md`, `CLAUDE.md`, `agents/README.md`), the five non-hook agent files (`code-implementer`, `codebase-discovery`, `deployment-operator`, `mavis`, `test-engineer`), the `agent-plan` slash command, `git-push-pr-preflight.sh`, `cbm-session-reminder`, and the `validate-agent-artifact-write/` bundle (hook + 4 docs). |
| `template-only`   |     7 | `mcp.json.template`, `settings.json.template` (env / model / permissions / hooks wiring), `settings.json.template` (`statusLine` local-placeholder command — the user must either fill in a local script path or remove the block), `settings.json.template` (`enabledPlugins`), `settings.json.template` (`extraKnownMarketplaces`), `settings.json.template` (sandbox / language / theme / etc.), and the `agent-model-override-gate.py` hook (depends on `CLAUDE_AGENT_MODEL_OVERRIDE_SECRET_FILE`). |
| `missing`         |     1 | `skills/` is empty by design; reusable skill methodology lives in `assets/skills/`. |
| `skipped`         |     0 | No live runtime state committed. The validator enforces this. |
| `blocked`         |     4 | `agents/code-reviewer.md` (frontmatter `PreToolUse` hook command points at `~/.claude/hooks/validate-agent-artifact-write/hook.mjs code-reviewer`; the bundle has no auto-install), `agents/task-planner.md` (same hook prerequisite, `~/.claude/hooks/validate-agent-artifact-write/hook.mjs task-planner`), the `cbm-code-discovery-gate` hook (augments via `codebase-memory-mcp` binary that is not in this repo), and the `new-feature` slash command (depends on `~/.claude/scripts/instantiate-feature.sh` and `~/.claude/baselines/durable-workflow-v1/...` that are not in this repo). |

**The committed `*.template` files are NOT live runnable.** Copy the
template to its live filename (`settings.json`, `mcp.json`) on the
target machine and fill in the placeholders before the runtime loads
them. The validator at `scripts/validate_repo_structure.py` enforces
that no live `settings.json` or `mcp.json` is committed.

**Specific truthfulness notes** (called out by the audit):

- The `statusLine` block in `settings.json.template` is a
  local-placeholder block. The `command` is the placeholder
  `<path-to-local-statusline-script-on-this-machine>`. The template
  ships no value Claude Code can run as-is; the user must either
  replace the placeholder with the absolute path of a statusline
  script they have installed locally, or remove the whole
  `statusLine` block to disable the statusline. The committed
  `hooks/` directory in this repo contains
  `agent-model-override-gate.py`, `git-push-pr-preflight.sh`,
  `cbm-code-discovery-gate`, `cbm-session-reminder`, and the
  `validate-agent-artifact-write/` bundle only; no statusline
  script is committed. The row is now **template-only** because
  the only thing the template owns is the local-placeholder form
  of the command — the script itself is the user's prerequisite.
- The `/new-feature` slash command invokes
  `~/.claude/scripts/instantiate-feature.sh` and reads templates from
  `~/.claude/baselines/durable-workflow-v1/baseline/docs/specs/_template/`.
  Both are external to this repo. The `~`-relative form is expanded at
  runtime; the command will not work on a clean clone.

## Boundaries

- `agents/`, `commands/`, `hooks/` here are Claude Code runtime files.
  They are not reusable across runtimes; reusable material lives in
  `assets/` at the repo root.
- `settings.json.template` and `mcp.json.template` are templates only. Do
  not commit a live `settings.json` or `mcp.json` with secrets, absolute
  local paths, model routing, or machine-specific values. Copy the
  template and fill it in locally.
- `hooks/` is Claude Code's hook format. Do not assume the same executable
  format works for Codex or oh-my-pi; those live under their own targets.

## How to land a change here

1. Drop runtime-native files into the matching subdirectory.
2. If the file holds secrets, local paths, model routing, or
   machine-specific values, use the `*.template` filename and document the
   copy step. Hooks that call external binaries must read the binary path
   from an environment variable (e.g. `$CODEBASE_MEMORY_MCP_BIN`) with a
   documented placeholder default; do not hard-code an absolute user path.
3. Do not promote material from `targets/claude-code/` into `assets/`. If
   the material is reusable across runtimes, it belongs in `assets/` from
   the start, not retrofitted here.
