# MCP server card: codebase-memory-mcp

> Shared MCP assets are **cards**, not runtime wiring. This file is
> a server card. The actual `mcp.json` / `config.toml` /
> `omp.config.json` wiring lives in `targets/<tool>/` and is the
> owning tool's job. See `assets/README.md` for the category
> contract.

## Purpose

Expose the codebase-memory-mcp knowledge graph tools to agents so
they can answer structural code questions (callers, callees, type
definitions, route/channel wiring, cross-service calls) without
blind `grep` or guesswork. The server indexes a repository and
returns graph-backed answers for queries the agent would otherwise
have to reconstruct from text search.

This is the **server contract** an agent can rely on. The transport
and invocation shape are documented below; the runtime wiring that
loads the server on a specific machine is the tool's job, not
this card's.

## Transport

- **Transport**: stdio. The runtime spawns a single binary per
  session and exchanges MCP messages on its stdin/stdout.
- **Invocation shape**: a single command-line binary the runtime
  invokes with no required arguments. The binary path is
  **machine-specific** and is filled in by the target wiring, not
  by this card.
- **No network listener**: the binary does not expose an HTTP or
  SSE port. All communication is over the runtime's stdio pipe.

## Tools and resources exposed

The card names the operations an agent can rely on; the
implementation behind them is owned by the server binary. Names
follow the `mcp__codebase-memory-mcp__<tool>` convention used by
Claude Code; other runtimes will translate the namespace to their
own MCP wire format.

- `index_repository(repo_path, mode?)` — index a repository into
  the knowledge graph. Modes trade freshness for speed.
- `search_graph(query)` — find nodes by name pattern, label, or
  question pattern.
- `trace_path(symbol, mode)` — follow call chains, data flow, or
  cross-service links starting from a symbol.
- `get_code_snippet(qualified_name)` — fetch the exact source of
  a symbol at precise ranges.
- `query_graph(query)` — run an arbitrary Cypher query against
  the graph.
- `get_architecture(aspects)` — return a structured map of the
  repository's architecture for the requested aspects.
- `search_code(pattern)` — graph-augmented text search; preferred
  over raw `ripgrep` for code questions.
- `manage_adr(project, mode, content?, sections?)` — create or
  update an Architecture Decision Record inside the project.
- `list_projects` / `index_status` / `delete_project` —
  administrative operations on indexed projects.

The card documents the contract; new operations may be added by
updating this card and the corresponding server binary in the same
release.

## Environment requirements

- The binary path is provided by the target wiring (env var, config
  block, or absolute path). The card does **not** ship a path and
  must never inline one.
- `CODEBASE_MEMORY_MCP_BIN` is the conventional override env var
  used by hook scripts (see the
  `codebase-memory-search-augment` policy in `assets/hooks/`); the
  card does not require it but the hook policy does.
- The server reads the repository it indexes directly from disk.
  No remote source is required. No network credentials are needed
  for read-only indexing.
- The card does **not** require any additional environment
  variables to operate. The target wiring decides whether the
  binary path is read from the shell environment, a secret store,
  or a runtime secret reference.

## Security notes

- The server is local and runs with the same user permissions as
  the runtime that spawned it. It does not require elevated
  privileges.
- The server reads the repository at index time. The
  `disallowedTools` lists of read-only agents (such as
  `code-reviewer` and `task-planner`) keep the server usable in
  advisory mode only.
- Hook scripts that call this server (see the
  `codebase-memory-search-augment` policy in `assets/hooks/`) must
  resolve the binary path from `$CODEBASE_MEMORY_MCP_BIN` with a
  documented placeholder default. The committed source must not
  hard-code an absolute user path.
- Treat the graph output as **advisory**. Confirm any code change
  against the live repository before applying it; the graph can be
  stale if indexing is behind the working tree.
- The server does not log or exfiltrate indexed content. It does
  not phone home.

## Target compatibility

- **Claude Code**: wired via
  `targets/claude-code/mcp.json.template`. Copy to `mcp.json` and
  fill in the binary path on the target machine. The committed
  template documents the wiring shape; the runtime path is
  placeholder.
- **Codex**: wired via `targets/codex/config.toml.template`. The
  Codex MCP block follows the TOML shape; the binary path is
  placeholder.
- **oh-my-pi**: wired via
  `targets/oh-my-pi/omp.config.json.template` (when the harness
  exposes an MCP block).

The card itself is tool-agnostic. Compatibility notes are pointers
to the target wiring; they are not instructions to commit live
config.

## Runtime config ownership

The card is the source of truth for the **server's contract**:
transport, tool list, environment requirements, security posture,
and the operations an agent may call.

The target wiring under `targets/<tool>/` is the source of truth
for **this machine's** invocation: binary path, args, env values,
and per-machine tokens.

Keep the two roles separate. If a new operation is added, update
the card. If a token or path changes, update the target wiring
only.

## Relationship to other assets

- Hook policy: `assets/hooks/codebase-memory-search-augment.md`
  (PreToolUse augmenter that runs `hook-augment` on Grep/Glob
  invocations).
- Hook policy: `assets/hooks/codebase-memory-session-reminder.md`
  (SessionStart reminder that the agent should call these tools
  first for any code exploration).
- Role: `assets/agents/role-blueprints.md` (each role that may
  read the graph lists this card as a composed asset).
- Pack: `assets/packs/codebase-memory-assisted-workflow.md`
  (composition of the card, the two hook policies, and the
  relevant rules).
