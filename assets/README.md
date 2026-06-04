# Reusable assets

Low-maintenance catalog of agent configuration material that is safe to share across runs and tools. Each entry below names what belongs in that category and what does not. When in doubt, leave the material in `inbox/` until it has a clear home.

Categories that are **out of scope** for `assets/`: shared `commands/`, `prompts/`, and `tips/` directories. Those are runtime-tool concerns, not reusable assets — a single tool owns the prompt, command, or tip, so it belongs in `targets/<tool>/`, not here.

## skills

Agent Skills standard workflows. **Belongs:** workflow descriptions, prompts, and references authored against the Agent Skills open standard so any compatible runtime can load them. **Does not belong:** target-specific rewrites of a standard workflow. A target-specific override is allowed only when the standard workflow has a real runtime incompatibility with a tool, and the override must be minimal, isolated, and clearly justified.

## agents

Role blueprints. **Belongs:** a description of the role, the inputs it consumes, the outputs it produces, and the skills and other assets it composes. **Does not belong:** runtime-native subagent files (JSON/TOML/YAML a tool's launcher reads directly) — those are tool concerns and live in `targets/<tool>/`.

## mcp-servers

MCP server cards. **Belongs:** a short card per server that names the transport, what tools and resources it exposes, and any preconditions for use. **Does not belong:** runtime-native JSON/TOML/YAML config snippets that wire a server into a specific tool — that wiring is the tool's job and lives in `targets/<tool>/`.

## hooks

Lifecycle policy patterns. **Belongs:** a description of which lifecycle event is being observed, what the policy says should happen, and the conditions under which the policy applies. **Does not belong:** executable runtime hooks, scripts, or extension code that a tool loads and runs — those are runtime code and belong in `targets/<tool>/`.

## rules

Repository-level conventions. **Belongs:** short, declarative rules an agent should follow when working in this repo (style, structure, naming, do/do-not lists). **Does not belong:** tool configuration, executable code, or anything that ties to a single runtime.

## packs

Lightweight composition notes. **Belongs:** a short document that names a set of existing skills, agents, rules, and MCP cards that travel together for a common use case, plus a one-line rationale for the grouping. **Does not belong:** copies or inlined versions of the underlying assets — packs only link, they never own.
