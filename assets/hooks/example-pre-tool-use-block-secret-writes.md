# Example: hook policy pattern (lifecycle intent)

This file is a minimal example of a **shared hook policy pattern**. It
documents the lifecycle event, the policy, and the conditions under
which the policy applies. It is **not** an executable hook.

> See `assets/README.md` for the category contract. Executable hook
> scripts and runtime hook wiring live in `targets/<tool>/hooks/`
> (and `targets/oh-my-pi/extensions/` for the harness). This directory
> is for policy descriptions only.

## Lifecycle event

`PreToolUse` — fires before a runtime invokes a tool on the agent's
behalf. The runtime surfaces the tool name, the structured input, and
the session context, and asks the policy whether to allow, deny, or
modify the invocation.

## Policy

When the tool is a file write (`write_file`, `edit_file`, or the
runtime's equivalent), deny the invocation if any of the following
match the resolved file path or contents:

- The path resolves under `inbox/` and the resolved content looks
  like a runtime-native config (`.json`, `.toml`, `.yaml`, `.yml`).
  Inbox is for unclassified material; promoting it into `assets/` or
  `targets/` is a maintainer decision, not a side effect of a write.
- The path resolves under a live sensitive config file in
  `targets/<tool>/` (`settings.json`, `mcp.json`, `config.toml`,
  `omp.config.json`). Live configs are uncommitted by design; the
  agent must not write to them.
- The content matches a known secret shape (private key block,
  `ghp_*` / `github_pat_*` token, AWS access key, etc.). The policy
  fails closed even if the agent believes the value is safe.

## When the policy applies

- Applies to every agent invocation that runs against this repo, on
  every runtime that supports a `PreToolUse` hook.
- Applies regardless of the tool that issues the write. A `write_file`
  call and a shell `tee` invocation both flow through the same
  policy once the runtime normalises them.
- Does not apply to reads, listings, or searches. `PreToolUse` fires
  only on mutating tool calls.

## What this file is not

- It is not a script. There is no shell, Python, or JavaScript body.
  The runtime reads the policy description, not this directory's
  bytes.
- It is not wiring. A runtime-native hook config (`PreToolUse` entry
  in `targets/<tool>/settings.json` or the equivalent in
  `config.toml` / `omp.config.json`) is what actually loads and
  enforces the policy. That wiring lives in `targets/`.
- It is not a tool-specific extension. Claude Code, Codex, and
  oh-my-pi each implement `PreToolUse` in their own format. The
  policy stays runtime-agnostic; each target translates it.

## Reuse across runtimes

If a target cannot enforce the policy exactly as written (for
example, the runtime has no `PreToolUse` hook, or the runtime cannot
inspect shell `tee` arguments), the workaround belongs in
`targets/<tool>/hooks/` and must justify the divergence in its first
paragraph. Do not weaken the shared policy to fit a single runtime.
