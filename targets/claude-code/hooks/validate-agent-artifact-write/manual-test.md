# Manual test

Allowed temp artifact sample:

```bash
printf '{"hook_event_name":"PreToolUse","tool_name":"Write","tool_input":{"file_path":"%s/claude-agent-artifacts/code-reviewer-sample.md","content":"x"}}' "$TMPDIR" | node hook.mjs code-reviewer
```

Blocked path sample:

```bash
printf '{"hook_event_name":"PreToolUse","tool_name":"Write","tool_input":{"file_path":"/tmp/not-allowed.md","content":"x"}}' | node hook.mjs code-reviewer
```
