# Custom Agent Definitions

Source-only, opt-in specialist agent definitions for Claude Code. Not auto-installed.

## What this is

Reusable, version-controlled agent definitions that users can adopt by copying to `~/.claude/agents/` or a project `.claude/agents/` directory. This directory is a distribution source and design guide, not a workflow runtime.

Each agent is a standalone specialist. Claude Code routes to agents primarily from frontmatter `description`, so descriptions should state the trigger, scope, and negative cases clearly. Prompt bodies define specialist behavior and quality bars; they do not define transport, orchestration, or task-state protocols.

## Baseline specialists

| Agent | Model | Effort | Max turns | Role |
|---|---:|---:|---:|---|
| `task-planner` | opus | inherit | 15 | Principal engineer/TPM for ambiguous work; turns fuzzy intent into executable, verifiable plans. |
| `code-implementer` | haiku | xhigh | 35 | Senior product engineer for constrained high-signal patches and smallest provable production changes. |
| `test-engineer` | haiku | xhigh | 25 | Staff test engineer for behavior proof, false-positive prevention, and RED/GREEN evidence quality. |
| `code-reviewer` | sonnet | xhigh | 30 | Principal hostile reviewer for correctness, security, scope, and evidence failures. |
| `deployment-operator` | haiku | xhigh | 15 | Senior SRE for documented operations where authorization, rollback, and health evidence are explicit. |
| `mavis` | haiku | inherit | 20 | Mavis Team Plan operator for bounded worker/verifier execution evidence without final acceptance. |

## Agent definition shape

Baseline agents use a short hard prompt shape:

```text
## Role
## Boundaries
## Workflow
## What you produce
## Artifact and final handoff
```

`## Artifact and final handoff` is always the last section. It defines the Bookend XML transport contract for gate-critical fields only. Agent-specific evidence remains agent-specific.

## Design principles

- Keep `description` precise: action, scope, and when not to use the agent.
- Keep prompts role-focused: what the specialist does, how it works, and what it must not do.
- Do not encode orchestration pipelines in agent definitions.
- Do not make one specialist depend on another specialist to be useful.
- Do not add transport-specific handoff protocols unless the agent's explicit purpose is orchestration.
- Prefer repository evidence over memory or generic stack assumptions.

## Tool and permission matrix

| Agent | Write/Edit | Bash | MCP codebase | Git commit |
|---|---:|---:|---:|---:|
| `task-planner` | temp artifacts only via scoped hook | no | yes | no |
| `code-implementer` | production plus focused tests | targeted smoke/codegen/test commands | yes | explicit authorization only |
| `test-engineer` | test assets only | test commands only | yes | no |
| `code-reviewer` | temp artifacts only via scoped hook | no | yes | no |
| `deployment-operator` | no | documented ops only | no | no |
| `mavis` | no | no | no (Mavis MCP only) | no |

## Routing and workspace rules

- Custom agent calls should omit explicit `model` unless a signed override is present. If the caller must pass a model, it must match the agent frontmatter.
- Tasks that must change the caller's current workspace must not use worktree isolation. If worktree isolation is used, the handoff must report the workspace root and changed-file roots.
- Review handoffs must start with `PASS`, `FAIL`, or `BLOCKED: ...`. Missing verdict means the review gate is blocked, not passed or failed.
- `mavis` is a Team Plan operator. It must use Mavis MCP Team Plan tools rather than direct file edits, shell commands, or non-Team-Plan fallback paths.
- Mavis timeout or empty worker output does not prove no side effects occurred. Treat side effects as unknown until reconciled with plan/session evidence.
- Mavis verifier output is execution evidence, not an independent review gate.

Project memory is only a clue; any referenced file, command, function, or rule must be verified against the current repository.

## Deployment safety

`deployment-operator` may run documented read-only status checks when the request includes a clear target and runbook/script/CI source. Mutating deployment, release, rollback, or infrastructure actions require explicit current-session authorization plus the safety gates in the agent definition.

The operator must block rather than infer when approval gates, rollback procedure, environment, or documented command source are unclear.

## Claude Code model parameters and actual control

Agent frontmatter declares intended `model`, `effort`, `permissionMode`, and related runtime fields. Current Claude Code tool schema or UI behavior may still inject a `model` parameter when calling subagents.

Hook-level model gates are the effective enforcement layer. Callers should omit explicit model parameters for custom agents unless a signed override is present. If Claude Code schema or UI behavior injects a model, it must match the frontmatter model; otherwise follow hook feedback and retry once with the required model.

## Adding a specialist agent

New specialists should use precise `description` routing and role-focused prompts. Add orchestration language only for agents whose explicit job is orchestration.

## Installation

```bash
# Copy selected agents to your user-level agents directory
cp ~/.claude/baselines/durable-workflow-v1/distribution/agents/*.md ~/.claude/agents/

# Or copy individual agents
cp ~/.claude/baselines/durable-workflow-v1/distribution/agents/task-planner.md ~/.claude/agents/
```

## Relationship to other layers

- `global/standards/core-standard.md` — core verification and review gates.
- These agents do not replace global runtime principles; they provide opt-in specialists.


## Final handoff rules

- First line is `STATUS: ...`.
- Envelope attributes are only `agent`, `status`, `workspace`, and `artifact`.
- Final line is `<handoff-end ... />`.
- No text appears after the end marker.
- Workspace is observed absolute path, or `UNVERIFIED` with `BLOCKED`.
- Default artifact path is `$TMPDIR/claude-agent-artifacts/<agent>-*.md`.
- Project artifacts require explicit request and gitignored `.claude/agent-artifacts/`.

## Read-only artifact writes

`code-reviewer` and `task-planner` may use `Write` only for temp artifacts. This is safe only with the scoped user hook. Prompt-only restrictions are not sufficient. Do not use `Bash` to create artifacts.
