# Hook policy pattern: agent artifact write scope

> Shared hook assets are **policy notes**, not runtime wiring. This
> file is a lifecycle intent for a `PreToolUse` gate that scopes
> the `Write` tool for read-only agents to a single, isolated
> directory. See `assets/README.md` for the category contract.
> Executable hook scripts and runtime hook wiring live in
> `targets/<tool>/hooks/`.

## Lifecycle event

`PreToolUse` (matcher: `Write`) — fires before the runtime
executes a `Write` tool call on the agent's behalf. The runtime
surfaces the target path, the content to be written, and the
session context, and asks the policy whether to allow, deny, or
modify the invocation.

This pattern is a **scope gate** for agents whose role is
read-only. It exists because prompt-only restrictions on `Write`
are not sufficient: a hostile or distracted model can still call
`Write` with a surprising path. The hook is the effective
enforcement layer.

## Policy

When the matcher fires, the policy applies the following rules in
order. A violation blocks the invocation with exit code 2 and a
short remediation hint printed to stderr.

1. **Tool name is `Write`.** The matcher guarantees this in
   Claude Code today; a runtime that maps the policy to a
   different tool name must update the matcher accordingly.
2. **The path is absolute.** Relative paths are denied. A
   read-only agent should not be guessing where to write.
3. **The path is under `$TMPDIR/claude-agent-artifacts/`.** The
   base directory is computed as
   `path.resolve(process.env.TMPDIR || os.tmpdir(), 'claude-agent-artifacts')`.
   Paths outside that root, or paths that resolve to a parent
   traversal (`..`), are denied.
4. **The filename matches `<agent>-<token>.md`.** The `<agent>`
   prefix is the role's frontmatter `name` slug, supplied as the
   hook's first positional argument. The `<token>` is
   `[A-Za-z0-9._-]+`. Any other filename is denied. This
   prevents a read-only agent from naming a temp artifact after
   someone else's role or after a non-`.md` extension.
5. **The content is not validated by this policy.** Content
   validation, review quality, and test evidence quality are
   out of scope; the scope gate does not check them.

## Allowed path shape

`$TMPDIR/claude-agent-artifacts/<agent>-<token>.md` is the only
allowed shape. The agent's role supplies the `<agent>` prefix at
invocation time; the runtime-native hook wiring
(`targets/claude-code/settings.json.template` →
`hooks.PreToolUse[matcher=Write]`) passes the role name as a
positional argument to the executable.

## When the policy applies

- Applies to every `Write` invocation made by an agent whose
  role is declared read-only (`code-reviewer`, `task-planner`,
  and any future role that adds the same gate). The runtime
  wires the gate through the role's frontmatter `hooks` block
  or through a global `PreToolUse` matcher.
- Applies regardless of session type. Main and sub-sessions are
  both subject to the gate.
- Does not apply to other tool types. `Read`, `Edit`, `Bash`,
  `Grep` — all have their own gates and are out of scope for
  this pattern. In particular, the gate does not stop an
  agent from using `Edit` to mutate a file; agents that need
  that guarantee must add it to their `disallowedTools` list.
- Does not apply to project persistent artifacts. An agent
  that needs to write a project artifact should not be
  read-only; this gate is the wrong tool for that case.

## What this file is not

- It is not a script. The runtime reads the policy description,
  not this directory's bytes.
- It is not a content gate. The policy only checks path and
  filename; it does not check what the agent is writing.
- It is not a tool-specific extension. The policy stays
  runtime-agnostic; each target translates it. A future
  runtime that wants the same behaviour wires its own scope
  gate that reads this policy and applies the same checks in
  its own way.

## Reuse across runtimes

If a target cannot enforce the policy exactly as written (for
example, the runtime has no `PreToolUse` matcher for `Write`, or
the runtime cannot normalise a relative path), the workaround
belongs in `targets/<tool>/hooks/` and must justify the
divergence in its first paragraph. Do not weaken the shared
policy to fit a single runtime.

A common divergence is **the temp directory**: a runtime that
uses a different temp convention (for example, a per-tenant
scratch directory) maps the policy's `$TMPDIR` step to its own
convention. The shape of the policy — "absolute path under a
known root, filename matches `<agent>-<token>.md`" — is
portable.

## Relationship to other assets

- Composed by: `assets/agents/role-blueprints.md`
  (`code-reviewer` and `task-planner` rely on this gate).
- Pack: `assets/packs/agent-blueprint-distribution.md`.
