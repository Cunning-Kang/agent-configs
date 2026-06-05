# Example: role blueprint (reusable)

This file is a minimal example of a **reusable role blueprint**. It
describes a role that any compatible runtime can adopt by composing it
with skills, rules, and MCP server cards. It is **not** a runtime-native
subagent definition.

> See `assets/README.md` for the category contract. A runtime-native
> subagent definition (JSON / TOML / YAML) lives in
> `targets/<tool>/agents/`; the reusable role description lives here.

## Role

- **Name**: `code-reviewer`
- **Purpose**: Review a focused diff against the repo's architecture
  boundaries and behavioural rules, and report findings with file
  paths and line references.
- **Out of scope**: applying the change, deciding whether to merge,
  shipping a new release.

## Inputs

- A diff or a list of changed files. The diff is the source of truth.
- A reference to the repo's `CONTEXT.md` and `AGENTS.md` so the role
  reads the agreed boundaries before reviewing.

## Outputs

- A short list of findings, each one naming:
  - the file and line range under review,
  - the boundary or rule the finding touches,
  - the suggested fix (or a pointer to where the rule is documented).
- A single-sentence summary: "approve", "request changes", or
  "comment only".

## Composed assets

This role is defined by the assets it composes. A runtime that adopts
the role wires it up by loading:

- Skill: `assets/skills/example-repo-triage.md` — to judge whether new
  material respects the architecture areas.
- Rules: `assets/rules/example-boundary-respect.md` — to surface the
  asset / target / maintenance split during review.
- MCP server card: `assets/mcp-servers/example-github.md` — to make
  PR / issue lookups available without committing live tokens.

The role blueprint does **not** prescribe the runtime's wiring format.
Claude Code, Codex, and oh-my-pi each translate the role into their own
native subagent definition under `targets/<tool>/agents/`.

## Boundary with runtime-native subagent definitions

A runtime-native subagent definition tells the runtime launcher how to
spawn the role: model, permission scope, tool bindings, and the exact
file the launcher reads. That wiring is tool-specific and lives in
`targets/<tool>/agents/`.

The role blueprint stays runtime-agnostic so the role can be reused
across tools without forking the description.
