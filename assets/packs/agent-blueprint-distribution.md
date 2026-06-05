# Pack: agent blueprint distribution

> See `assets/README.md` for the category contract. A pack is a
> composition note: it **links** to existing assets and never
> copies or inlines them. A pack is not an installable bundle.

## What this pack is for

Distribute the reusable role blueprints in
`assets/agents/role-blueprints.md` to a runtime subagent launcher
without forking the role description, and keep the launcher's
gates honest through the matching hook policies. The pack wires
the role catalog, the gate hook policies, and the boundary rules
together so a runtime that adopts a role also adopts the gates
that make the role safe to invoke.

## Composed assets

- **Role blueprints**:
  [`assets/agents/role-blueprints.md`](../agents/role-blueprints.md)
  — the catalog of reusable roles (code-implementer,
  code-reviewer, task-planner, test-engineer, deployment-operator,
  codebase-discovery). The catalog is runtime-agnostic; each
  runtime translates one blueprint into its own launcher-readable
  format.
- **Hook policy**:
  [`assets/hooks/agent-model-override.md`](../hooks/agent-model-override.md)
  — the `PreToolUse` (matcher: `Agent`) gate that ensures the
  subagent launcher respects the role's declared `model` unless a
  signed override is present.
- **Hook policy**:
  [`assets/hooks/agent-artifact-write-scope.md`](../hooks/agent-artifact-write-scope.md)
  — the `PreToolUse` (matcher: `Write`) gate that scopes the
  `Write` tool for read-only roles
  (`code-reviewer`, `task-planner`) to
  `$TMPDIR/claude-agent-artifacts/<agent>-*.md`.
- **Hook policy**:
  [`assets/hooks/git-push-pr-preflight.md`](../hooks/git-push-pr-preflight.md)
  — the `PreToolUse` (matcher: `Bash`) gate that runs a
  push/PR preflight (clean working tree, up-to-date branch,
  green CI, no blocked patterns) before any push or PR-opening
  command. The `code-implementer` and `deployment-operator` roles
  rely on this gate to keep the blast radius honest.
- **Rule**:
  [`assets/rules/example-boundary-respect.md`](../rules/example-boundary-respect.md)
  — the boundary rule that keeps the role catalog in
  `assets/agents/` separate from the runtime subagent files in
  `targets/<tool>/agents/`.
- **Rule**:
  [`assets/rules/no-shared-commands-prompts-tips.md`](../rules/no-shared-commands-prompts-tips.md)
  — the rule that prevents a future pack from accidentally
  promoting a runtime command into the shared layer.

## Rationale

A role blueprint alone is not safe to invoke. The model
override gate, the artifact-write scope gate, and the push/PR
preflight gate are the enforcement layers that make the role
behave the way the role description claims. A runtime that
adopts the role without the gates ends up with a role that
promises one thing and runs another.

The pack also keeps the role description and the gates in
their proper homes. The role description lives in
`assets/agents/role-blueprints.md`; the gate policies live in
`assets/hooks/`; the runtime wiring (the file the launcher
reads, the matcher the runtime matches on, the timeout, the
status message) lives in `targets/<tool>/`. A runtime that
adopts the pack translates the policy into its own wiring
without touching the role description or the gate policy.

## Boundaries

- The pack adds **no** new content. Every behaviour it describes
  lives in the assets it links to.
- The pack is **not** an installable bundle. A runtime that adopts
  the pack still loads each asset by its own path.
- The pack does **not** override any asset. If a link disagrees
  with the asset it points at, the asset wins; update the pack.
- The pack does **not** prescribe the runtime's wiring format.
  Claude Code, Codex, and oh-my-pi each translate the role and
  the gates into their own launcher-readable format.
- The pack does **not** include a runtime command, prompt, or
  tip. Roles that need a runtime-specific entry point belong in
  `targets/<tool>/commands/`, not in this pack.
