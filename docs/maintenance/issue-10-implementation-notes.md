# Issue #10 implementation notes

Mapping from each new asset to the inventory classification that
authorised its promotion, plus a one-line summary of the
behaviour change each file produces. Read together with
`docs/maintenance/runtime-config-inventory.md` (the inventory
that is the source of truth) and `assets/README.md` (the catalog
that lists the new entries).

## What was promoted

| New asset | Inventory row | Why it is reusable |
| --- | --- | --- |
| `assets/agents/role-blueprints.md` | `agents/*.md` — `migrate` to `assets/agents/` if reusable | The seven Claude Code subagents encode roles (code-implementer, code-reviewer, task-planner, test-engineer, deployment-operator, codebase-discovery, mavis) that are useful across runtimes. The blueprint keeps the role description runtime-agnostic; the runtime-specific frontmatter (model, hooks, color) stays in `targets/claude-code/agents/`. |
| `assets/mcp-servers/codebase-memory-mcp.md` | `.mcp.json` — `template` to `targets/claude-code/mcp.json.template`; the **server knowledge** is `migrate` to `assets/mcp-servers/` | The transport, tool list, env requirements, and security posture of the codebase-memory-mcp server are stable across runtimes. The card documents them; the template owns only the binary path. |
| `assets/hooks/agent-model-override.md` | `hooks/<script>.py` — `migrate` to `targets/claude-code/hooks/`; the **policy** is `migrate` to `assets/hooks/` | The model-gate policy (model must match frontmatter unless a signed override is present) is portable. The executable gate stays in `targets/claude-code/hooks/agent-model-override-gate.py`. |
| `assets/hooks/git-push-pr-preflight.md` | same as above | The push/PR preflight (clean tree, up to date, green CI, no blocked patterns, explicit authorization) is a portable lifecycle policy. The shell implementation stays in `targets/claude-code/hooks/git-push-pr-preflight.sh`. |
| `assets/hooks/codebase-memory-search-augment.md` | same as above | The Grep/Glob augmenter that calls the codebase-memory-mcp server and never blocks is a portable policy. The shell implementation stays in `targets/claude-code/hooks/cbm-code-discovery-gate`. |
| `assets/hooks/codebase-memory-session-reminder.md` | same as above | The SessionStart reminder that names the graph tools in priority order is a portable policy. The shell implementation stays in `targets/claude-code/hooks/cbm-session-reminder`. |
| `assets/hooks/agent-artifact-write-scope.md` | same as above | The `Write` scope gate that confines read-only agents to `$TMPDIR/claude-agent-artifacts/<agent>-*.md` is a portable policy. The Node implementation stays in `targets/claude-code/hooks/validate-agent-artifact-write/hook.mjs`. |
| `assets/skills/promote-reusable-material.md` | `skills/<portable>/SKILL.md` — `migrate` to `assets/skills/` if reusable | The standard workflow for promoting inventory material into the shared asset catalog is itself a reusable Agent Skills standard workflow: it consumes an inventory, routes by category contract, and verifies the structure gate. |
| `assets/rules/no-shared-commands-prompts-tips.md` | new behavioural rule, complementary to `example-boundary-respect.md` | Pins down the one shape of "almost-promoted" material (commands, prompts, tips) that must not become a shared asset. Composes with the boundary-respect rule and is portable to any future `CLAUDE.md` / `AGENTS.md`. |
| `assets/packs/codebase-memory-assisted-workflow.md` | new composition note | Links the codebase-memory-mcp card, the two codebase-memory hook policies, the `promote-reusable-material` skill, the boundary-respect rule, and the role blueprints. |
| `assets/packs/agent-blueprint-distribution.md` | new composition note | Links the role catalog, the three enforcement gates (model override, artifact write scope, push/PR preflight), and the two boundary rules. |

## What was NOT promoted and why

- **`commands/agent-plan.md` and `commands/new-feature.md`** —
  inventory classifies these as `migrate` to
  `targets/claude-code/commands/`, not to `assets/`. Slash
  commands are Claude-Code-specific; they stay in the target.
- **Live `settings.json` and `mcp.json` values** — inventory
  classifies these as `template` (machine-specific). The
  templates in `targets/claude-code/*.template` are already in
  place; the live files are not committed. No promotion needed.
- **Executable hook scripts** — inventory classifies these as
  `migrate` to `targets/claude-code/hooks/`. Executable code
  stays in the target; only the policy descriptions move to
  `assets/hooks/`.
- **Runtime subagent frontmatter blocks** — the frontmatter
  (`disallowedTools`, `model`, `hooks`, `color`, `maxTurns`,
  `permissionMode`, `memory`, `effort`) is tool-specific. The
  role description is the only part promoted to
  `assets/agents/role-blueprints.md`; the frontmatter stays in
  `targets/claude-code/agents/*.md`.

## Why no shared `commands/`, `prompts/`, `tips/` were created

Issue #10 acceptance criterion is explicit: "Shared commands,
prompts, and tips directories are not introduced." The
classification in the inventory already routes these to
`targets/<tool>/commands/` (or simply does not invent the
category), so no such directory was created in `assets/` or at
the repo root. The new rule
`assets/rules/no-shared-commands-prompts-tips.md` documents the
rule for future slices.

## Boundary verification

Each new file respects the asset shape for its category:

- `assets/mcp-servers/*.md` — markdown only. No JSON/TOML/YAML
  wiring.
- `assets/hooks/*.md` — markdown only. No executable scripts.
- `assets/agents/*.md` — role blueprints only. No runtime-native
  subagent definitions.
- `assets/packs/*.md` — composition notes only. Links to
  existing assets; never copies or inlines.
- `assets/skills/*.md` — Agent Skills standard workflows. Frontmatter
  block declares the standard contract.
- `assets/rules/*.md` — declarative, runtime-agnostic rules.

`scripts/validate_repo_structure.py` should pass on the new tree
without modification. No new category was added; the existing
six categories cover the new entries.
