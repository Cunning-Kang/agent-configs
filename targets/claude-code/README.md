# Claude Code target

Runtime landing area for Claude Code. This directory is owned by Claude Code;
its contents may be rewritten by the tool at any time and are not a stable
contract. See `CONTEXT.md` at the repo root for the area role.

## Layout

| Path                | Role                                                                        |
| ------------------- | --------------------------------------------------------------------------- |
| `CLAUDE.md`         | Direct behavior entrypoint loaded by Claude Code when it enters this tree.  |
| `settings.json.template` | Template for machine-specific settings. Copy to `settings.json` to use. |
| `agents/`           | Runtime-native subagent definitions Claude Code loads directly.            |
| `commands/`         | Slash-command definitions owned by Claude Code.                            |
| `skills/`           | Runtime-specific skill overrides and tool-local skill material.            |
| `hooks/`            | Executable hook implementations in Claude Code's hook format.               |
| `mcp.json.template` | Template for MCP server wiring. Copy to `mcp.json` to use.                 |

## Boundaries

- `agents/`, `commands/`, `skills/`, `hooks/` here are Claude Code runtime
  files. They are not reusable across runtimes; reusable material lives in
  `assets/` at the repo root.
- `settings.json.template` and `mcp.json.template` are templates only. Do not
  commit a live `settings.json` or `mcp.json` with secrets, absolute local
  paths, model routing, or machine-specific values. Copy the template and
  fill it in locally.
- `hooks/` is Claude Code's hook format. Do not assume the same executable
  format works for Codex or oh-my-pi; those live under their own targets.

## How to land a change here

1. Drop runtime-native files into the matching subdirectory.
2. If the file holds secrets, local paths, model routing, or machine-specific
   values, use the `*.template` filename and document the copy step.
3. Do not promote material from `targets/claude-code/` into `assets/`. If the
   material is reusable across runtimes, it belongs in `assets/` from the
   start, not retrofitted here.
