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
  the agent set. None of these reference absolute local paths.
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
("migrate to `assets/skills/` if reusable across runtimes"). This target
keeps no skill content of its own; `skills/` is empty by design until a
Claude-Code-specific override is needed.

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
