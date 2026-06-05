---
name: promote-reusable-material
description: |
  Promote genuinely reusable material from a runtime configuration
  inventory into the shared asset catalog (assets/skills, assets/agents,
  assets/mcp-servers, assets/hooks, assets/rules, assets/packs). Use
  when a runtime inventory exists, the material is already classified
  as reusable, and the task is to land the reusable subset without
  dragging per-tool material into the shared layer.
---

# Skill: promote-reusable-material

> Agent Skills standard workflow. Authored against the Agent Skills
> open standard so any compatible runtime can load it. See
> `assets/README.md` for the category contract. Per-tool overrides
> belong under `targets/<tool>/skills/` and must justify any
> divergence from this standard in their first paragraph.

## Frontmatter

The YAML block at the top of this file is the Agent Skills standard
contract. A runtime that implements the standard loads the skill
from this directory without any extra wiring.

## Workflow

1. **Start from an inventory.** The inventory (typically
   `docs/maintenance/runtime-config-inventory.md`) classifies each
   candidate path as `migrate`, `template`, `skip`, or `archive`.
   This skill consumes the `migrate` rows; the others are out of
   scope here. Do not invent classifications. The inventory is the
   source of truth.
2. **Decide the target category per row.** Read the inventory's
   "Target location once migrated" column. If it points under
   `assets/`, the material is reusable; if it points under
   `targets/<tool>/`, the material is per-tool and stays in the
   target.
3. **Match the material shape to the category contract.** A
   reusable workflow → `assets/skills/`. A reusable behavioural
   constraint → `assets/rules/`. A reusable agent concept →
   `assets/agents/` (role blueprint, **not** a runtime-native
   subagent definition). MCP server knowledge → `assets/mcp-servers/`
   (markdown server card, no JSON/TOML/YAML wiring). Lifecycle
   policy → `assets/hooks/` (markdown policy note, no executable
   script). A composition of existing assets →
   `assets/packs/` (links only, no copy or inline).
4. **Refuse to promote the wrong shape.** A Claude-Code-native
   slash command is not a shared asset. A runtime-native subagent
   frontmatter block is not a role blueprint. A live
   `settings.json` / `mcp.json` / `config.toml` /
   `omp.config.json` is not a server card. Stop and route the
   material to its proper home when the shape does not match.
5. **De-sanitise checks.** Reject any promotion that would copy
   secrets, sessions, histories, caches, logs, transcripts,
   databases, backups, local tokens, install IDs, native binaries,
   or unreviewed migrations. The inventory classifies all of these
   as `skip` for a reason; honour it.
6. **Land and cross-link.** Add the new asset with a short header
   that names the role, the inputs, the outputs, the boundaries,
   and the assets it composes. Cross-link from `assets/README.md`
   when a new entry is added so the catalog stays the source of
   truth. Do not duplicate content already in
   `example-*` reference assets; promote with a fresh filename
   only.
7. **Verify the structure gate.** After promotion, the repository
   structure validator (`scripts/validate_repo_structure.py`) must
   still pass. New entries must respect:
   - `assets/mcp-servers/` contains `.md` only.
   - `assets/hooks/` contains `.md` only.
   - `assets/agents/` contains role blueprints (`.md`).
   - `assets/packs/` contains composition notes (`.md`).
   - No new shared `commands/`, `prompts/`, or `tips/` directory
     anywhere.

## When a target-specific override is allowed

A target-specific override is allowed **only** when the shared
skill has a real runtime incompatibility with a specific tool, and
**only** under these conditions:

- The override lives under `targets/<tool>/skills/`, never under
  `assets/`.
- The override is minimal — it adjusts the standard workflow for
  the runtime incompatibility, nothing else.
- The override is isolated — it does not leak target-specific
  behaviour into the shared skill or into other runtimes.
- The override is justified — its first paragraph names the
  standard workflow it diverges from and the runtime incompatibility
  that motivates the divergence.

If the proposed override is not justified by a real incompatibility,
do not create one. Fix the shared skill instead, or leave the
divergence as a target-specific note in
`targets/<tool>/README.md`.

## Inputs

- A classified inventory (`docs/maintenance/runtime-config-inventory.md`
  in this repo) with rows marked `migrate` and a target location
  under `assets/<category>/`.
- A clear promotion task (issue, ticket, or scoped request)
  naming the rows to promote and the acceptance criteria.

## Outputs

- One or more new files under `assets/<category>/`, each one
  short, declarative, and shaped to its category.
- A `STATUS: ...` handoff naming changed files, the inventory
  rows consumed, and a verification result for the structure gate.

## Boundaries

- This skill **does not** migrate per-tool material into the
  shared layer. Per-tool rows stay in `targets/<tool>/`.
- This skill **does not** invent classifications. The inventory
  is the only source of truth for what is reusable.
- This skill **does not** copy live runtime values. Secrets,
  tokens, model routing, absolute local paths, and machine-specific
  values stay off the shared layer; they belong in
  `targets/<tool>/<file>.template`, not in `assets/`.
- This skill **does not** create runtime-native subagent
  definitions, hook executables, MCP JSON/TOML/YAML wiring, slash
  commands, prompts, or tips. Those shapes belong elsewhere.
