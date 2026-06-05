# Example: shared skill (Agent Skills standard)

This file is a minimal example of a **reusable** skill authored against the
Agent Skills open standard. It demonstrates the shape of a shared skill and
records the rule for when a target-specific override is allowed.

> See `assets/README.md` for the category contract. A shared skill is
> standard workflow material that any compatible runtime can load; it is
> **not** a runtime-native subagent definition, hook, or config snippet.

## Frontmatter

```yaml
---
name: example-repo-triage
description: |
  Triage an incoming issue or change request against this repo's
  architecture boundaries (assets vs targets vs maintenance docs).
  Use when the user asks whether a piece of material belongs in
  `assets/`, `targets/`, `inbox/`, or `archive/`.
---
```

The frontmatter is the Agent Skills standard contract. A runtime that
implements the standard loads the skill from this directory without any
extra wiring.

## Workflow

1. Read `CONTEXT.md` at the repo root to refresh the area roles.
2. If the material is reusable across runtimes, place it under
   `assets/<category>/`. Reusable categories are listed in
   `assets/README.md`.
3. If the material is tool-specific (config, hook code, slash command,
   runtime subagent definition), place it under `targets/<tool>/` —
   never under `assets/`.
4. If the material is unclassified, place it in `inbox/`. Promotion to
   `assets/` or `targets/` happens only after the home is clear.
5. If the material is retired, move it to `archive/`. Do not delete
   silently.

## When a target-specific override is allowed

A target-specific override is allowed **only** when the shared skill has a
real runtime incompatibility with a specific tool, and **only** under
these conditions:

- The override lives under `targets/<tool>/skills/`, never under
  `assets/`.
- The override is minimal — it adjusts the standard workflow for the
  runtime incompatibility, nothing else.
- The override is isolated — it does not leak target-specific behaviour
  into the shared skill or into other runtimes.
- The override is justified — its first paragraph names the standard
  workflow it diverges from and the runtime incompatibility that
  motivates the divergence.

If the proposed override is not justified by a real incompatibility,
do not create one. Fix the shared skill instead, or leave the
divergence as a target-specific note in `targets/<tool>/README.md`.
