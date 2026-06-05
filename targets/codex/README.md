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

## Runnability status

Every committed file in this target is classified by the issue #12
audit. The full per-file table lives in
`docs/maintenance/runtime-runnability-audit.md`; this section is the
short version.

**Bucket counts** (per logical row in the audit):

| Bucket          | Count | What it means here                                                                 |
| --------------- | ----: | ---------------------------------------------------------------------------------- |
| `runnable`      |     2 | `README.md` and `AGENTS.md` (pure documentation).                                  |
| `template-only` |     1 | `config.toml.template` (sanitized shape; not loaded by Codex on this machine).    |
| `missing`       |     4 | `agents/`, `commands/`, `hooks/`, `skills/` are intentionally empty; the local Codex runtime root is **absent on this machine** (see `docs/maintenance/runtime-config-inventory.md`). |
| `skipped`       |     0 | No live runtime state committed. The validator enforces this.                      |
| `blocked`       |     0 | Nothing is blocked; there is nothing to block because no real Codex source was migrated. |

**The committed `config.toml.template` is NOT live runnable.** Copy
the template to `~/.codex/config.toml` (or wherever the local Codex
install expects it) and fill in the placeholders before Codex loads
it. The validator at `scripts/validate_repo_structure.py` enforces
that no live `config.toml` is committed.

**Runtime source absence.** No Codex hooks, agents, commands, or
skills exist on this machine or in this repo. The audit records this
explicitly so a reader does not assume the template plugs into a
populated runtime. The `config.toml.template` and the four empty
subdirectories document the boundary; no real source is invented.
When a Codex root later appears on this machine, the issue #8
inventory classification should be applied to it and this audit
re-issued.
