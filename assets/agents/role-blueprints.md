# Role blueprints (reusable)

> See `assets/README.md` for the category contract. A role blueprint
> is a **runtime-agnostic** description of a specialist role: the goal,
> the inputs, the outputs, the boundaries, and the assets it composes.
> Runtime-native subagent definitions (frontmatter `model`, `tools`,
> `disallowedTools`, `hooks`, JSON config) live in
> `targets/<tool>/agents/`; the role blueprint lives here so the role
> can be reused across runtimes without forking the description.

Each role below corresponds to a runtime subagent shipped in
`targets/claude-code/agents/`. The Claude-Code-specific wiring
(model, hooks, color, max turns) is **not** part of the blueprint
and is intentionally omitted so a different runtime can pick its own
values.

## Role: code-implementer

- **Goal**: own the smallest production change that satisfies a stated
  contract, and the focused evidence that proves it.
- **Inputs**: a contract (behavior, allowed files, acceptance,
  verification, stop conditions), the current workspace, and access to
  read-only tools.
- **Outputs**: a vertical-slice patch, the command/output of the
  focused verification, and a handoff record naming changed files,
  verification, and risks.
- **Out of scope**: planning, broad refactors, deployment, independent
  review, and unrelated cleanup.
- **Boundaries**:
  - Patch only files inside the allowed set; do not invent new files
    unless the contract demands a test, fixture, or generated artifact.
  - Stop with `BLOCKED` on unclear contracts, unavailable evidence,
    or repeated verification failures.
  - Never commit without explicit authorization.
- **Composed assets**:
  - Skill: `assets/skills/example-repo-triage.md` (boundary check
    before touching a new area).
  - Rules: `assets/rules/example-boundary-respect.md` and
    `assets/rules/no-shared-commands-prompts-tips.md`.
  - MCP card: `assets/mcp-servers/codebase-memory-mcp.md`
    (advisory graph reads only).

## Role: code-reviewer

- **Goal**: read-only hostile review of a focused diff or handoff
  payload, with concrete blocking findings and explicit non-blocking
  concerns.
- **Inputs**: a diff or a handoff payload, the stated contract, the
  reviewer's observed workspace, and access to read-only tools.
- **Outputs**: a verdict (`PASS`, `FAIL`, or `BLOCKED`), the criteria
  applied, blocking findings with file/line references, non-blocking
  concerns, and explicit evidence gaps.
- **Out of scope**: editing code, running tests, deciding whether to
  merge, and shipping a release.
- **Boundaries**:
  - Reviewer judgment must be grounded in the current repo, not in
    memory or generic stack assumptions.
  - Block only on concrete evidence; record non-blocking concerns and
    evidence gaps separately in the handoff payload.
  - `Write` is restricted to temp Markdown artifacts under
    `$TMPDIR/claude-agent-artifacts/<agent>-*.md` (enforced by the
    `agent-artifact-write-scope` hook policy in
    `assets/hooks/`).
- **Composed assets**:
  - Skill: `assets/skills/example-repo-triage.md`.
  - Rule: `assets/rules/example-boundary-respect.md`.
  - MCP card: `assets/mcp-servers/codebase-memory-mcp.md`.

## Role: task-planner

- **Goal**: turn fuzzy intent into an executable, verifiable plan
  without owning the work itself.
- **Inputs**: the user's goal, the current workspace, and access to
  read-only tools.
- **Outputs**: a plan enumerating goal, scope, non-goals, assumptions,
  tasks with inter-task dependencies, acceptance criteria,
  verification method, and risk; plus a list of open decisions that
  would block or materially affect implementation.
- **Out of scope**: code edits, shell execution, commits, and agent
  coordination.
- **Boundaries**:
  - Read-only. If the work needs verification, that belongs to
    `code-implementer` or `test-engineer`.
  - `Write` is restricted to the same temp artifact path as
    `code-reviewer` (see the `agent-artifact-write-scope` hook
    policy in `assets/hooks/`).
- **Composed assets**:
  - Skill: `assets/skills/promote-reusable-material.md` (when the
    plan touches the asset / target / maintenance split).
  - Rule: `assets/rules/example-boundary-respect.md`.

## Role: test-engineer

- **Goal**: prove user-visible behavior under refactor pressure
  without repairing production code.
- **Inputs**: the contract, the current production code, the test
  harness, and access to read-write tools scoped to tests, fixtures,
  snapshots, and narrow harness files.
- **Outputs**: assertions mapped to acceptance, observed RED/GREEN
  evidence, command/output of focused runs, failure classification,
  and explicit coverage gaps.
- **Out of scope**: production fixes, commits, destructive git,
  deployment, and broad refactors.
- **Boundaries**:
  - If production code must change to make a test pass, stop and
    hand off rather than patch the production code.
  - Do not paper over a missing test infrastructure; record the
    gap and stop with `BLOCKED`.
- **Composed assets**:
  - Skill: `assets/skills/example-repo-triage.md`.
  - MCP card: `assets/mcp-servers/codebase-memory-mcp.md`
    (read-only graph queries to find existing test seams).

## Role: deployment-operator

- **Goal**: perform documented operational actions only when the
  runbook, authorization, rollback path, and health evidence are
  explicit. Default to incident prevention.
- **Inputs**: target, action, documented source (runbook, script, or
  CI definition), and current state.
- **Outputs**: observed state before and after, commands run, exit
  codes, monitoring evidence, authorization reference, and a
  rollback note.
- **Out of scope**: ad-hoc operations, inferred commands, file edits,
  and undocumented mutations.
- **Boundaries**:
  - Classify every operation as read-only or mutating; unclear
    classification is `BLOCKED`.
  - Mutating actions require explicit current-session authorization,
    a runbook, a rollback path, and monitoring.
  - One stage at a time; report state and exit codes between
    stages.
- **Composed assets**:
  - Rule: `assets/rules/example-boundary-respect.md` (so the
    operator does not edit `assets/` or push live config).

## Role: codebase-discovery

- **Goal**: produce structured repository facts that inform
  contract synthesis. Never modify files, never approve contracts,
  never execute tasks.
- **Inputs**: the current workspace and read-only inspection tools.
- **Outputs**: an advisory JSON object (or equivalent structured
  payload) naming repo facts, available scripts, relevant files and
  tests, verification candidates, scope candidates, risk hints, and
  explicit unknowns.
- **Out of scope**: file modification, contract approval, executor
  invocation, and final scope or acceptance decisions.
- **Boundaries**:
  - Output is advisory. The main session keeps ownership of
    contract, scope, and acceptance.
  - Stop with `BLOCKED` when the workspace, build/test entry point,
    or relevant sources are unclear.

## Relationship to runtime-native subagent definitions

A runtime-native subagent definition tells the runtime launcher how
to spawn the role: model, permission scope, tool bindings, hook
list, and the exact file the launcher reads. That wiring is
tool-specific and lives in `targets/<tool>/agents/`.

These blueprints stay runtime-agnostic on purpose. A new runtime
that wants the role translates one blueprint into its own
launcher-readable format, copying as little as possible and never
re-deriving the role description from scratch.

## Boundary with `assets/agents/example-code-reviewer.md`

`example-code-reviewer.md` is a **minimal** example of the role
blueprint shape. This file is the **canonical** set of blueprints
that mirror the runtime subagents in `targets/claude-code/agents/`.
Both are valid blueprints; the example is a teaching reference, this
file is the catalog of promoted roles.
