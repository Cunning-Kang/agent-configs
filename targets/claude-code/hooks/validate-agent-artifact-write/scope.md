# Scope

## In scope

- Validate `Write.file_path` for read-only agent artifact writes.
- Allow only absolute temp artifact paths under `$TMPDIR/claude-agent-artifacts/<agent>-*.md`.

## Out of scope

- Content validation.
- Review quality.
- Test evidence quality.
- Directory creation.
- Project persistent artifacts.

## Failure mode

Exit `2` blocks unsafe writes.
