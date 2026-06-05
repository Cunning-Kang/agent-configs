# agent-configs

Personal AI coding agent configuration asset library and target landing repository for Claude Code, Codex, and oh-my-pi.

This repo is **not** a stable universal contract, schema, or full configuration-management system. It is a working stash of reusable assets and a place agents drop runtime material.

## Layout

- `assets/` — reusable agent configuration material (skills, agents, MCP server cards, hook policy patterns, rules, packs). See `assets/README.md` for the catalog and per-category boundaries.
- `targets/` — runtime landing areas where tools deposit their own files.
- `scripts/` — local helper scripts (including the structure validator described below).
- `inbox/` — untriaged material awaiting classification.
- `archive/` — retired or superseded material kept for reference.
- `docs/maintenance/` — maintenance docs (issue tracker, triage labels, domain conventions, and the runtime runnability audit).

## Entry points
- Humans: `README.md` (this file).
- Asset catalog: `assets/README.md`.
- Claude Code: `CLAUDE.md`.
- Codex / generic agents: `AGENTS.md`.
- Architecture: `CONTEXT.md`.
- Runtime runnability audit: `docs/maintenance/runtime-runnability-audit.md` (issue #12).

## Out of scope for reusable assets

Shared `commands/`, `prompts/`, and `tips/` directories are not part of the reusable asset area. A command, prompt, or tip is owned by a single runtime tool and belongs in `targets/<tool>/`, not in `assets/`.

## Validation

Run the structure validator to confirm the repository keeps the agreed
architecture and safety boundaries:

```
python3 scripts/validate_repo_structure.py
```

The script enforces the boundaries recorded in `CONTEXT.md` and
`assets/README.md`:

- the top-level architecture areas exist;
- `assets/` contains only the agreed reusable categories
  (`skills/`, `agents/`, `mcp-servers/`, `hooks/`, `rules/`, `packs/`);
- shared `commands/`, `prompts/`, and `tips/` asset directories never appear
  under `assets/`;
- each runtime target landing area exposes its expected template config
  file and does not commit a live sensitive config file
  (`settings.json`, `mcp.json`, `config.toml`, `omp.config.json`);
- `assets/mcp-servers/` contains only server cards — no runtime-native
  config snippets (`.json` / `.toml` / `.yaml` / `.yml`);
- `assets/hooks/` contains only policy notes (`.md`) — no executable
  hook scripts.

Each failure prints the boundary name and the offending path on its own
line, and the script exits non-zero on any violation. Focused unit tests
for the validator live at
`scripts/test_validate_repo_structure.py` and can be run with
`python3 -m unittest scripts.test_validate_repo_structure -v`.

