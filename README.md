# agent-configs

Personal AI coding agent configuration asset library and target landing repository for Claude Code, Codex, and oh-my-pi.

This repo is **not** a stable universal contract, schema, or full configuration-management system. It is a working stash of reusable assets and a place agents drop runtime material.

## Layout

- `assets/` — reusable agent configuration material (skills, agents, MCP server cards, hook policy patterns, rules, packs). See `assets/README.md` for the catalog and per-category boundaries.
- `targets/` — runtime landing areas where tools deposit their own files.
- `scripts/` — local helper scripts.
- `inbox/` — untriaged material awaiting classification.
- `archive/` — retired or superseded material kept for reference.
- `docs/maintenance/` — maintenance docs (issue tracker, triage labels, domain conventions).

## Entry points
- Humans: `README.md` (this file).
- Asset catalog: `assets/README.md`.
- Claude Code: `CLAUDE.md`.
- Codex / generic agents: `AGENTS.md`.
- Architecture: `CONTEXT.md`.

## Out of scope for reusable assets

Shared `commands/`, `prompts/`, and `tips/` directories are not part of the reusable asset area. A command, prompt, or tip is owned by a single runtime tool and belongs in `targets/<tool>/`, not in `assets/`.

