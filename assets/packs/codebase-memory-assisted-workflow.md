# Pack: codebase-memory-assisted workflow

> See `assets/README.md` for the category contract. A pack is a
> composition note: it **links** to existing assets and never
> copies or inlines them. A pack is not an installable bundle.

## What this pack is for

Use the codebase-memory knowledge graph as the first source of
truth for any code-exploration, navigation, or refactor-proposal
task. The pack wires the MCP server, the lifecycle hooks, the
shared skill, and the boundary rules together so a runtime does
not have to re-derive the composition on every run.

## Composed assets

- **MCP card**:
  [`assets/mcp-servers/codebase-memory-mcp.md`](../mcp-servers/codebase-memory-mcp.md)
  — the server contract (transport, tools, env requirements,
  security posture, target compatibility, runtime config
  ownership). The card is the source of truth for the server's
  contract; the target wiring is the source of truth for the
  binary path on a specific machine.
- **Hook policy**:
  [`assets/hooks/codebase-memory-search-augment.md`](../hooks/codebase-memory-search-augment.md)
  — the `PreToolUse` augmenter that adds graph context to every
  `Grep|Glob` invocation, never blocks, and resolves the binary
  through `$CODEBASE_MEMORY_MCP_BIN`.
- **Hook policy**:
  [`assets/hooks/codebase-memory-session-reminder.md`](../hooks/codebase-memory-session-reminder.md)
  — the `SessionStart` reminder that names the graph tools the
  agent should reach for first, in order, for any code
  exploration.
- **Skill**:
  [`assets/skills/promote-reusable-material.md`](../skills/promote-reusable-material.md)
  — the standard workflow for promoting reusable material from
  an inventory into the shared asset catalog. Use this skill
  when the workflow touches the asset / target / maintenance
  split.
- **Rule**:
  [`assets/rules/example-boundary-respect.md`](../rules/example-boundary-respect.md)
  — the boundary rule that keeps the runtime landing area
  (`targets/<tool>/`) separate from the shared asset area
  (`assets/<category>/`).
- **Role blueprints**:
  [`assets/agents/role-blueprints.md`](../agents/role-blueprints.md)
  — every read-only role in the catalog (code-reviewer,
  task-planner) lists the MCP card as a composed asset.

## Rationale

The codebase-memory-mcp server is genuinely reusable across
runtimes: it exposes a stable contract (tools, transport, env
requirements) that any MCP-aware runtime can adopt. The two
hook policies encode the same behaviour in two places
(session-start reminder, per-search augmenter) so the agent
sees the policy once and then on every search. The boundary
rule keeps the runtime landing area and the shared asset area
separate, so the runtime can rewrite its own wiring without
touching the shared layer.

A runtime that adopts the pack loads each asset by its own
path. The pack itself adds no new content.

## Boundaries

- The pack adds **no** new content. Every behaviour it describes
  lives in the assets it links to.
- The pack is **not** an installable bundle. A runtime that adopts
  the pack still loads each asset by its own path and still
  wires each hook through its own `PreToolUse` / `SessionStart`
  matcher.
- The pack does **not** override any asset. If a link disagrees
  with the asset it points at, the asset wins; update the pack.
- The pack does **not** commit a live server config. The card
  names the server contract; the target wiring under
  `targets/<tool>/` is the only place a runtime's binary path
  or token is recorded.
