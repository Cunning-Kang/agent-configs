# validate-agent-artifact-write

Enforces read-only artifact writes for global subagents.

- Event: `PreToolUse`
- Tool: `Write`
- Scope: user-level source-only hook
- Allowed path: `$TMPDIR/claude-agent-artifacts/<agent>-*.md`
- Denied by default: repo paths and `.claude/agent-artifacts/`

## Install

1. Copy this directory to `~/.claude/hooks/validate-agent-artifact-write/`.
2. Merge the settings snippet manually only if needed.
3. Restart Claude Code if hook loading requires it.

No auto-install happens from this baseline.
