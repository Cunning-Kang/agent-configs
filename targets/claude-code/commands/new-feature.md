---
description: |
  Create a new feature spec directory from the _template skeleton.
  Invokes ~/.claude/scripts/instantiate-feature.sh to create docs/specs/<feature-slug>/
  from the canonical baseline cache at ~/.claude/baselines/durable-workflow-v1.
  Use this after /init-claude-workflow when starting any new feature, bugfix, or refactor
  that needs a spec/plan/review/verify structure.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
argument-hint: <feature-slug>
---

Usage: Run `/new-feature <feature-slug>` directly — it invokes the script automatically.

What it does:
1. Confirm a feature slug was provided.
2. Invoke `~/.claude/scripts/instantiate-feature.sh <feature-slug>`.
3. Read template files from the canonical baseline cache at `~/.claude/baselines/durable-workflow-v1/baseline/docs/specs/_template/`
   (or `CLAUDE_WORKFLOW_BASELINE_PATH` if explicitly set).
4. Create `docs/specs/<feature-slug>/` from `_template/`.
5. Replace `<feature-slug>` placeholders in all generated files.
6. Skip if the feature directory already exists.

After instantiation, fill in:
- `spec.md`: Goal, Scope, Acceptance, Non-goals, Risks, Rollback
- `plan.md`: Execution Order, Steps, Risks/Blockers
- `tasks/T01-example.md`: Rename to match your first implementation step
- `review.md`: Fill in Reviewer before starting implementation
- `verify.md`: Add verification commands for each acceptance condition

Then continue with the Superpowers `/brainstorming` skill.

## Non-goals
- Do not sync the baseline cache.
- Do not upgrade an initialized repo.
- Do not overwrite an existing feature directory.
- Do not create git commits automatically.
