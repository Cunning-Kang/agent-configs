# Architecture

Core decisions for this repo.

## Purpose

Personal AI coding agent configuration asset library and target landing repository for Claude Code, Codex, and oh-my-pi.

## Scope of guarantees

This repo does **not** provide:
- a stable universal contract for agent configuration,
- a full configuration-management system,
- a versioned schema, or
- backwards-compatibility promises for anything under `targets/`.

It **is**:
- a working stash of reusable material (`assets/`),
- a place runtime tools drop their own files (`targets/`),
- a staging area for unclassified material (`inbox/`),
- a holding area for retired material (`archive/`),
- a home for local helper scripts (`scripts/`).

## Top-level areas

| Area | Role | Stability |
| ---- | ---- | --------- |
| `assets/` | Reusable configuration material. | Reusable across runs and tools. |
| `targets/` | Runtime landing areas for tool output. | Not a contract; contents may be rewritten by the owning tool. |
| `scripts/` | Local helper scripts. | Project-local utilities; not a public API. |
| `inbox/` | Untriaged material. | Transient. |
| `archive/` | Retired or superseded material. | Read-only reference. |
| `docs/maintenance/` | Issue tracker, triage labels, domain conventions. | Maintenance docs; not runtime config. |

## Boundaries

- `assets/` is for **reusable** material. Single-run artefacts go in `inbox/` then `targets/` or `archive/`.
- `targets/` is **per-tool**. Each tool owns its subdirectory and is free to rewrite it.
- `docs/maintenance/` holds repo maintenance docs (issue tracker usage, triage vocabulary, skill conventions). It is not consumed by any runtime tool as configuration.
- Runtime config assets and maintenance docs are kept in distinct trees on purpose. Do not mix them.

## Entry points

- `README.md` — human-facing overview.
- `CLAUDE.md` — Claude Code working rules.
- `AGENTS.md` — Codex and generic-agent working rules.
