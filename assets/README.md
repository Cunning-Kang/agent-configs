# Reusable assets

Low-maintenance catalog of agent configuration material that is safe to share across runs and tools. Each entry below names what belongs in that category and what does not. When in doubt, leave the material in `inbox/` until it has a clear home.

Categories that are **out of scope** for `assets/`: shared `commands/`, `prompts/`, and `tips/` directories. Those are runtime-tool concerns, not reusable assets — a single tool owns the prompt, command, or tip, so it belongs in `targets/<tool>/`, not here.

## skills

Agent Skills standard workflows. **Belongs:** workflow descriptions, prompts, and references authored against the Agent Skills open standard so any compatible runtime can load them. **Does not belong:** target-specific rewrites of a standard workflow. A target-specific override is allowed only when the standard workflow has a real runtime incompatibility with a tool, and the override must be minimal, isolated, and clearly justified.

### Catalog

- `example-repo-triage.md` — minimal example of a shared skill, including the rule for when a target-specific override is allowed.
- `promote-reusable-material.md` — standard workflow for promoting reusable material from a runtime configuration inventory into the shared asset catalog. Reads the inventory's `migrate` rows, routes by category contract, refuses the wrong shape, and verifies the structure gate.

## agents

Role blueprints. **Belongs:** a description of the role, the inputs it consumes, the outputs it produces, and the skills and other assets it composes. **Does not belong:** runtime-native subagent files (JSON/TOML/YAML a tool's launcher reads directly) — those are tool concerns and live in `targets/<tool>/agents/`.

### Catalog

- `example-code-reviewer.md` — minimal example of a role blueprint, including the boundary with runtime-native subagent definitions.
- `role-blueprints.md` — catalog of reusable role blueprints (code-implementer, code-reviewer, task-planner, test-engineer, deployment-operator, codebase-discovery) that mirror the runtime subagents shipped in `targets/claude-code/agents/`. Each blueprint is runtime-agnostic; the runtime-specific wiring lives in the target.

## mcp-servers

MCP server cards. **Belongs:** a short card per server that names the transport, what tools and resources it exposes, and any preconditions for use. **Does not belong:** runtime-native JSON/TOML/YAML config snippets that wire a server into a specific tool — that wiring is the tool's job and lives in `targets/<tool>/`.

### Catalog

- `example-github.md` — minimal example of a server card, including the runtime config ownership rule.
- `codebase-memory-mcp.md` — server card for the codebase-memory-mcp knowledge graph server. Names the transport (stdio), the tools and resources exposed (`index_repository`, `search_graph`, `trace_path`, `get_code_snippet`, `query_graph`, `get_architecture`, `search_code`, `manage_adr`, plus admin operations), the env requirements, the security posture, and the target-compatibility pointers to `targets/<tool>/`.

## hooks

Lifecycle policy patterns. **Belongs:** a description of which lifecycle event is being observed, what the policy says should happen, and the conditions under which the policy applies. **Does not belong:** executable runtime hooks, scripts, or extension code that a tool loads and runs — those are runtime code and belong in `targets/<tool>/hooks/`.

### Catalog

- `example-pre-tool-use-block-secret-writes.md` — minimal example of a hook policy pattern, including the rule for documenting a runtime divergence.
- `agent-model-override.md` — `PreToolUse` (matcher: `Agent`) policy. The subagent launcher's `model` must match the subagent's frontmatter `model` unless a signed override is present; the override marker is `CLAUDE_AGENT_MODEL_OVERRIDE_SECRET_FILE`.
- `git-push-pr-preflight.md` — `PreToolUse` (matcher: `Bash`) policy. Push and PR-opening commands must pass a preflight: remote is configured, working tree is clean, branch is up to date with upstream, required CI checks are green, no blocked patterns in the diff, and an explicit authorization is present in the current session.
- `codebase-memory-search-augment.md` — `PreToolUse` (matcher: `Grep|Glob`) policy. Augment every text search with graph context from the codebase-memory-mcp server; never block. Binary resolves through `$CODEBASE_MEMORY_MCP_BIN` with a documented placeholder default.
- `codebase-memory-session-reminder.md` — `SessionStart` (matcher: `startup|resume|clear|compact`) policy. Print a static reminder that names the graph tools the agent should reach for first, in order, for any code exploration.
- `agent-artifact-write-scope.md` — `PreToolUse` (matcher: `Write`) policy. Scope the `Write` tool for read-only agents (code-reviewer, task-planner) to `$TMPDIR/claude-agent-artifacts/<agent>-*.md`; deny by exit 2 on any other path, filename shape, or relative path.

## rules

Repository-level conventions. **Belongs:** short, declarative rules an agent should follow when working in this repo (style, structure, naming, do/do-not lists). **Does not belong:** tool configuration, executable code, or anything that ties to a single runtime.

### Catalog

- `example-boundary-respect.md` — minimal example of a reusable rule, including the consumption pattern for future `CLAUDE.md` or `AGENTS.md` composition.
- `no-shared-commands-prompts-tips.md` — rule that pins down the one shape of "almost-promoted" material that must not become a shared asset. A command, prompt, or tip is owned by a single runtime tool; do not invent a shared `commands/`, `prompts/`, or `tips/` directory at the repo root, under `assets/`, or as a sibling of `targets/<tool>/`.

## packs

Lightweight composition notes. **Belongs:** a short document that names a set of existing skills, agents, rules, and MCP cards that travel together for a common use case, plus a one-line rationale for the grouping. **Does not belong:** copies or inlined versions of the underlying assets — packs only link, they never own.

### Catalog

- `example-triage-pack.md` — minimal example of a pack, including the "pack is not an installable bundle" boundary.
- `codebase-memory-assisted-workflow.md` — composition of the codebase-memory-mcp card, the two codebase-memory hook policies, the `promote-reusable-material` skill, the boundary-respect rule, and the role blueprints. The pack wires them together so a runtime does not have to re-derive the composition on every run.
- `agent-blueprint-distribution.md` — composition of the role catalog, the three enforcement gates (model override, artifact write scope, push/PR preflight), and the two boundary rules. A runtime that adopts a role also adopts the gates that make the role safe to invoke.
