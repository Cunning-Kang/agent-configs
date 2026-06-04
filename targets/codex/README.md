# Codex target

Runtime landing area for Codex. This directory is owned by Codex; its
contents may be rewritten by the tool at any time and are not a stable
contract. See `CONTEXT.md` at the repo root for the area role.

## Layout

| Path                | Role                                                                  |
| ------------------- | --------------------------------------------------------------------- |
| `AGENTS.md`         | Direct behavior entrypoint loaded by Codex when it enters this tree.  |
| `config.toml.template` | Template for Codex configuration. Copy to `config.toml` to use.    |
| `agents/`           | Runtime-native subagent definitions Codex loads directly.             |
| `commands/`        | Slash-command definitions owned by Codex.                            |
| `hooks/`            | Executable hook implementations in Codex's hook format.               |
| `skills/`           | Runtime-specific skill overrides and tool-local skill material.       |

## Boundaries

- `agents/`, `commands/`, `hooks/`, `skills/` here are Codex runtime files.
  They are not reusable across runtimes; reusable material lives in
  `assets/` at the repo root.
- `config.toml.template` is a template only. Do not commit a live
  `config.toml` with secrets, absolute local paths, model routing, or
  machine-specific values. Copy the template and fill it in locally.
- `hooks/` is Codex's hook format. Do not assume the same executable format
  works for Claude Code or oh-my-pi; those live under their own targets.

## How to land a change here

1. Drop runtime-native files into the matching subdirectory.
2. If the file holds secrets, local paths, model routing, or machine-specific
   values, use the `*.template` filename and document the copy step.
3. Do not promote material from `targets/codex/` into `assets/`. If the
   material is reusable across runtimes, it belongs in `assets/` from the
   start, not retrofitted here.
