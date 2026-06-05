# Runtime configuration inventory (issue #8)

Read-only decision record. This document classifies major local runtime
configuration paths for Claude Code, Codex, and oh-my-pi as **migrate**,
**template**, **skip**, or **archive** so later migration slices can move
real configuration into the repository without guessing and without
committing sensitive runtime state.

This slice does not modify any live runtime configuration and does not
migrate any files. It only records the classification.

## Scope and method

| Runtime    | Local root inspected                       | Status   |
| ---------- | ------------------------------------------ | -------- |
| Claude Code | `~/.claude/`                              | present  |
| Codex       | `~/.codex/` (and `~/.config/codex/`, `~/.config/openai/`, `~/Library/Application Support/codex/`) | absent |
| oh-my-pi   | `~/.omp/`                                  | present  |

Inspection used `read`-equivalent directory listings and `find` on the
roots above. No file contents were copied into the repository, no
sensitive files were opened, and no runtime files were modified. Only
directory names, file basenames, and file sizes were recorded (sizes are
listed in the tables below as evidence that each entry is populated, not
as content).

The classification policy used throughout this document:

- **migrate** — non-sensitive, reusable, config-shaped material that
  belongs in `targets/<tool>/` (per-tool landing area) or in
  `assets/` (reusable material) once it has been sanitised and
  templatised.
- **template** — config-shaped material that is reusable in shape but
  carries machine-specific values (model routing, absolute paths,
  per-machine permissions) and must be reduced to a `*.template` file in
  `targets/<tool>/`.
- **skip** — live runtime state that must not be committed under any
  circumstance: secrets, tokens, sessions, transcripts, histories,
  caches, logs, local databases, backups, install IDs, plugin caches,
  daemon sockets, in-use plugin files.
- **archive** — retired, superseded, or orphaned material that is
  useful as a reference but is not part of the active config surface.
  It stays on the local machine and may be copied to `archive/` only
  after explicit, per-entry review.

## Repository boundary rules (enforce when migrating)

When a path is classified as **migrate** or **template**, the target
location is fixed by `CONTEXT.md` and `AGENTS.md`:

- Reusable config assets → `assets/` (one of `assets/skills/`,
  `assets/agents/`, `assets/mcp-servers/`, `assets/hooks/`,
  `assets/rules/`, `assets/packs/`).
- Per-tool landing and runtime target material →
  `targets/<tool>/`. Do not promote it into `assets/`.
- Untriaged material → `inbox/`.
- Retired material → `archive/`.
- Maintenance documentation such as this file → `docs/maintenance/`.
  Maintenance docs are not consumed by any runtime tool as
  configuration.

The `assets/hooks/` area is policy notes only (`.md`); executable hook
scripts live in `targets/<tool>/hooks/`. Slash commands and prompts
are per-tool and live in `targets/<tool>/commands/`, never at the repo
root.

The `*.template` filename convention is mandatory for any file that
may hold machine-specific values. The structure validator at
`scripts/validate_repo_structure.py` already enforces that no live
`sensitive` config file (`settings.json`, `mcp.json`, `config.toml`,
`omp.config.json`) is committed to `targets/`.

## Claude Code — `~/.claude/`

Major paths observed. Sizes are listed as evidence the file or
directory is populated, not as content.

| Path                                    | Bytes | Classification | Target location once migrated | Notes |
| --------------------------------------- | -----: | -------------- | ----------------------------- | ----- |
| `settings.json`                         |   8726 | **template**   | `targets/claude-code/settings.json.template` | Machine-specific model routing, permissions, env, and hook wiring. Redact to a template. |
| `.mcp.json`                             |    144 | **template**   | `targets/claude-code/mcp.json.template`     | Carries MCP transport and may carry tokens. Redact to a template. |
| `agents/*.md`                           |     —  | **migrate**    | `assets/agents/` only if reusable; otherwise `targets/claude-code/agents/` | Reusable agent specs belong in `assets/agents/`. Per-tool overrides stay in `targets/claude-code/agents/`. |
| `commands/*.md`                         |     —  | **migrate**    | `targets/claude-code/commands/`             | Slash commands are Claude Code-specific. Never create a shared `commands/` at the repo root. |
| `skills/<portable>/SKILL.md` and scripts|     —  | **migrate**    | `assets/skills/` if reusable across runtimes; otherwise `targets/claude-code/skills/` | Skills that came from a reusable marketplace belong in `assets/skills/`. Tool-local overrides stay in the target. |
| `hooks/<script>.py` / `<dir>/hook.mjs`  |     —  | **migrate**    | `targets/claude-code/hooks/`                | Hook implementations are Claude Code's hook format. Executable scripts only; the corresponding `.md` policy notes belong in `assets/hooks/`. |
| `plugins/` (top-level)                  |     —  | **skip**       | —                                            | Live plugin registration state. Not config. |
| `plugins/plugin-catalog-cache.json`     | 317085 | **skip**       | —                                            | Cached plugin catalog; downloaded, machine-local, not source of truth. |
| `plugins/cache/...`                     |     —  | **skip**       | —                                            | Plugin code cache, version-pinned by hash. Recreated by plugin install. |
| `plugins/cache/.../.in_use/<pid>`       |     —  | **skip**       | —                                            | Process-id locks. Live runtime state, not config. |
| `plugins/cache/.../.orphaned_at`        |     —  | **archive**    | `archive/claude-plugins-orphaned/` only if referenced | Marker file for orphaned plugin versions. Reference only, do not recreate. |
| `projects/**/*.jsonl`                   |     —  | **skip**       | —                                            | Session transcripts. Live runtime state. |
| `projects/**/subagents/*.jsonl`         |     —  | **skip**       | —                                            | Subagent transcripts. Live runtime state. |
| `projects/**/tool-results/*.json`       |     —  | **skip**       | —                                            | Captured tool call results. Live runtime state. |
| `sessions/`                             |     —  | **skip**       | —                                            | Session state. Live runtime state. |
| `session-env/<uuid>/`                   |     —  | **skip**       | —                                            | Per-session environment captures. Live runtime state. |
| `history.jsonl`                         |     —  | **skip**       | —                                            | Command / interaction history. Live runtime state. |
| `file-history/<uuid>/`                  |     —  | **skip**       | —                                            | File-snapshot history. Live runtime state. |
| `shell-snapshots/`                      |     —  | **skip**       | —                                            | Shell snapshot state. Live runtime state. |
| `jobs/<uuid>/state.json`, `exit-cause`  |     —  | **skip**       | —                                            | Job control state. Live runtime state. |
| `tasks/`                                |     —  | **skip**       | —                                            | Task list state. Live runtime state. |
| `teams/`                                |     —  | **skip**       | —                                            | Team / agent team runtime state. Live runtime state. |
| `backups/.claude.json.backup.<ts>`      |     —  | **skip**       | —                                            | Backups of machine-local config. Sensitive and machine-specific. |
| `daemon.log`                            |     —  | **skip**       | —                                            | Daemon log. Live runtime state. |
| `daemon/roster.json`                    |   1558 | **skip**       | —                                            | Daemon process roster. Live runtime state. |
| `.last-cleanup`                         |     —  | **skip**       | —                                            | Cleanup marker. Live runtime state. |
| `projects/` (top-level)                 |     —  | **skip**       | —                                            | Whole tree is per-machine session and transcript state. |

## Codex — local root

**Status: absent on this machine.** `~/.codex/`, `~/.config/codex/`,
`~/.config/openai/`, and `~/Library/Application Support/codex/` were
each checked and none exist. No Codex configuration is invented in
this document. The existing
`targets/codex/config.toml.template` already documents the
template-only contract; when a Codex root later appears on this
machine, the classification policy in this document should be applied
to it without modifying the template or the `targets/codex/`
landing area. No migration slice should be planned against Codex
paths until a local root is confirmed.

## oh-my-pi — `~/.omp/`

Major paths observed. Sizes are listed as evidence the file or
directory is populated, not as content.

| Path                                                                 | Bytes | Classification | Target location once migrated | Notes |
| -------------------------------------------------------------------- | -----: | -------------- | ----------------------------- | ----- |
| `agent/config.yml`                                                   |    986 | **template**   | `targets/oh-my-pi/omp.config.json.template` (shape re-expressed as JSON template) | Harness config. Carries model routing, runtime registration, and possibly local paths. Redact to a template. The committed `omp.config.json.template` already documents the expected shape. |
| `agent/models.yml`                                                   |    696 | **template**   | `targets/oh-my-pi/omp.config.json.template` (`model.routing` block) | Model routing is machine-specific. Fold into the harness config template. |
| `agent/extensions/<name>/index.ts`                                   |     —  | **migrate**    | `targets/oh-my-pi/extensions/<name>/`            | Extension source. oh-my-pi-specific format; do not move to `assets/`. |
| `agent/extensions/<name>/classification-helpers.ts`                  |     —  | **migrate**    | `targets/oh-my-pi/extensions/<name>/`            | Extension source. Same rule as above. |
| `agent/extensions/<name>/tests/**`                                   |     —  | **migrate**    | `targets/oh-my-pi/extensions/<name>/tests/`      | Extension tests. Keep alongside the extension under the target. |
| `agent/extensions/<name>/tests/run-tests.sh` and `*.test.mjs`        |     —  | **migrate**    | `targets/oh-my-pi/extensions/<name>/tests/`      | Test entry points. Keep alongside the extension. |
| `agent/sessions/<workspace>/<session-id>.jsonl`                      |     —  | **skip**       | —                                            | Session transcripts. Live runtime state. |
| `agent/sessions/<workspace>/<session-id>/*.jsonl`                    |     —  | **skip**       | —                                            | Sub-session transcripts. Live runtime state. |
| `agent/sessions/<workspace>/<session-id>/*.md`                       |     —  | **skip**       | —                                            | Captured agent outputs that may include secrets. Live runtime state. |
| `agent/sessions/<workspace>/<session-id>/*.bash.log` / `*.bash-original.log` / `*.read.log` | — | **skip** | —                                            | Captured tool logs. Live runtime state. |
| `agent/terminal-sessions/<tty>`                                      |     —  | **skip**       | —                                            | Terminal session captures. Live runtime state. |
| `agent/agent.db`, `agent.db-wal`, `agent.db-shm`                     |     —  | **skip**       | —                                            | Local SQLite database. Live runtime state. |
| `agent/models.db`, `models.db-wal`, `models.db-shm`                  |     —  | **skip**       | —                                            | Local SQLite database. Live runtime state. |
| `agent/history.db`, `history.db-wal`, `history.db-shm`               |     —  | **skip**       | —                                            | Local SQLite database. Live runtime state. |
| `agent/autoqa.db`, `autoqa.db-wal`, `autoqa.db-shm`                  |     —  | **skip**       | —                                            | Local SQLite database. Live runtime state. |
| `cache/github-cache.db*`                                             |     —  | **skip**       | —                                            | Local cache database. Live runtime state. |
| `logs/omp.<date>.log`                                                |     —  | **skip**       | —                                            | Runtime logs. Live runtime state. |
| `logs/<hashed-audit-log>.json`                                        |     —  | **skip**       | —                                            | Audit log. Live runtime state. |
| `natives/<version>/pi_natives.darwin-arm64.node`                     |     —  | **skip**       | —                                            | Native binary. Platform- and version-specific; must be installed by the tool, not committed. |
| `install-id`                                                         |     37  | **skip**       | —                                            | Per-machine install identifier. Must never be committed. |

## Sensitive and live runtime material

The following categories are unconditionally **skip** (or **template**
when their shape is reusable) regardless of which runtime owns them.
None of these are eligible to be migrated as live values.

- Secrets, tokens, API keys, provider credentials, and env overrides
  that may carry any of the above.
- Sessions, session transcripts, subagent transcripts, and tool-result
  captures.
- Command, file, and shell histories.
- Caches, plugin caches, and `.in_use` lock files.
- Logs and audit logs.
- Local databases (SQLite and similar) and their WAL/SHM files.
- Backups of machine-local configuration.
- Install IDs and per-machine identifiers.
- Native binaries and platform-specific compiled artefacts.

## Migration sequencing (for downstream slices)

This inventory does not perform migration. The intended follow-up
order, derived from the classifications above, is:

1. Sanitise and convert `~/.claude/settings.json` to
   `targets/claude-code/settings.json.template` (template).
2. Sanitise and convert `~/.claude/.mcp.json` to
   `targets/claude-code/mcp.json.template` (template).
3. Migrate reusable Claude Code `agents/`, `commands/`, `skills/`,
   and `hooks/` to `assets/` (reusable) or `targets/claude-code/`
   (tool-local), per the boundary rules above (migrate).
4. Sanitise and convert `~/.omp/agent/config.yml` and
   `~/.omp/agent/models.yml` to
   `targets/oh-my-pi/omp.config.json.template` (template).
5. Migrate `~/.omp/agent/extensions/<name>/` source to
   `targets/oh-my-pi/extensions/<name>/` (migrate).
6. Defer all `**/sessions/**`, `**/transcripts/**`, `**/*.db*`,
   `**/logs/**`, `**/backups/**`, `**/cache/**`, `**/.in_use/**`,
   `**/install-id`, and `**/natives/**` to skip.
7. Defer Codex until a local root exists on this machine.
