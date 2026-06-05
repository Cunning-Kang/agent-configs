# Hook policy pattern: agent model override

> Shared hook assets are **policy notes**, not runtime wiring. This
> file is a lifecycle intent: it names the event, the policy, the
> conditions under which the policy applies, and the boundary with
> the runtime-native hook that enforces it. See `assets/README.md`
> for the category contract. Executable hook scripts and runtime
> hook wiring live in `targets/<tool>/hooks/`.

## Lifecycle event

`PreToolUse` (matcher: `Agent`) — fires before a runtime invokes
its subagent launcher. The runtime surfaces the parent agent name,
the target subagent name, and the structured tool input, and asks
the policy whether to allow, deny, or modify the invocation.

This pattern is a **model-gating** policy. The runtime wants to
launch a subagent with a specific `model` parameter; the policy
decides whether that model matches the subagent's declared
`model` and whether a signed override is present.

## Policy

When a subagent launcher tool is invoked, the policy applies the
following rules in order:

1. **If the caller did not pass an explicit `model` parameter**,
   allow the invocation. Custom subagents declare their intended
   model in their own frontmatter; the runtime may inject a default
   that matches it, and that is the safe path.
2. **If the caller passed an explicit `model` parameter that
   matches the subagent's frontmatter `model`**, allow the
   invocation.
3. **If the caller passed an explicit `model` parameter that does
   not match the subagent's frontmatter `model`**, look for a
   signed override. The override marker is the presence and value
   of the `CLAUDE_AGENT_MODEL_OVERRIDE_SECRET_FILE` env var. If
   the env var points to a file that exists and is readable, and
   the file's contents include a valid signature, allow the
   invocation and record the override in the audit log.
4. **If the model does not match and no signed override is
   present**, deny the invocation with a non-zero exit. The
   runtime-native hook (see
   `targets/claude-code/hooks/agent-model-override-gate.py`)
   prints a short remediation hint and exits.

## When the policy applies

- Applies to every subagent invocation that runs against this
  repo, on every runtime that supports a `PreToolUse` matcher for
  `Agent` (Claude Code today; a future runtime that exposes the
  same matcher can adopt the same policy unchanged).
- Applies regardless of the parent session. Main and sub-sessions
  are both subject to the same gate.
- Does not apply to direct tool calls (file edits, shell
  commands, MCP calls). Those are gated by other policies.

## What this file is not

- It is not a script. There is no Python, shell, or JavaScript
  body. The runtime reads the policy description, not this
  directory's bytes.
- It is not wiring. A runtime-native hook config (a `PreToolUse`
  entry in `targets/claude-code/settings.json.template` or the
  equivalent in `config.toml` / `omp.config.json`) is what
  actually loads and enforces the policy. That wiring lives in
  `targets/`.
- It is not a tool-specific extension. Claude Code, Codex, and
  oh-my-pi each implement `PreToolUse` in their own format. The
  policy stays runtime-agnostic; each target translates it.

## Reuse across runtimes

If a target cannot enforce the policy exactly as written (for
example, the runtime has no `PreToolUse` hook, or the runtime
cannot read the parent agent's frontmatter), the workaround
belongs in `targets/<tool>/hooks/` and must justify the
divergence in its first paragraph. Do not weaken the shared
policy to fit a single runtime.

A common divergence is **the override file format**: the
`CLAUDE_AGENT_MODEL_OVERRIDE_SECRET_FILE` env var is a Claude
Code convention. Codex and oh-my-pi should map the same idea to
their own secret-resolution mechanism and document the mapping
in their target wiring. The policy itself — "model must match
frontmatter unless a signed override is present" — is portable.

## Relationship to other assets

- Composed by: `assets/agents/role-blueprints.md` (every custom
  role in that file inherits this gate).
- Pack: `assets/packs/agent-blueprint-distribution.md`.
