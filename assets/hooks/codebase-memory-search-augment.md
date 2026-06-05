# Hook policy pattern: codebase-memory search augment

> Shared hook assets are **policy notes**, not runtime wiring. This
> file is a lifecycle intent for a `PreToolUse` augmenter that
> runs against `Grep` and `Glob` invocations and adds graph-backed
> context to the agent's view. See `assets/README.md` for the
> category contract. Executable hook scripts and runtime hook
> wiring live in `targets/<tool>/hooks/`.

## Lifecycle event

`PreToolUse` (matcher: `Grep|Glob`) — fires before the runtime
executes a text search or glob on the agent's behalf. The runtime
surfaces the search pattern, the structured input, and the session
context.

This pattern is an **augmenter**, not a gate. It never blocks a
tool call. Its job is to surface the graph-backed answer that the
codebase-memory-mcp server (`assets/mcp-servers/codebase-memory-mcp.md`)
can give for the same query, so the agent uses graph reads first
and the text search second.

## Policy

When the matcher fires, the augmenter calls the codebase-memory-mcp
binary with `hook-augment` and the structured input. The binary
returns a short advisory block naming matching nodes, call chains,
or code snippets that the agent should consider alongside the text
search. The augmenter prints the advisory block to the agent's
context and exits 0.

Failure mode for the binary: silent. If the binary is missing,
unreadable, or returns a non-zero exit, the augmenter exits 0
without printing anything. The text search must still proceed; the
augmenter is best-effort.

## Resolution order for the binary

The augmenter resolves the codebase-memory-mcp binary in the
following order. Each step is checked; the first match wins.

1. `$CODEBASE_MEMORY_MCP_BIN` env var, when set and executable.
2. The placeholder default declared in the target wiring (a
   literal `<absolute-path-to-codebase-memory-mcp-binary-on-this-machine>`
   token that the runtime replaces on the target machine).
3. `$HOME/.local/bin/codebase-memory-mcp` as a last-resort default.

The committed source for the augmenter hook (see
`targets/claude-code/hooks/cbm-code-discovery-gate`) must never
hard-code an absolute user path. Hooks run in shells where
tilde expansion is not guaranteed, so `$HOME` is expanded
explicitly.

## When the policy applies

- Applies to every `Grep` and `Glob` invocation, on every runtime
  that supports a `PreToolUse` matcher for the tool.
- Applies regardless of the search pattern. The augmenter is
  pattern-agnostic; the server decides what is a useful advisory
  block.
- Does not apply to other tool types. `Read`, `Write`, `Edit`,
  `Bash` — all have their own gates and are out of scope for this
  pattern.
- Does not block. The augmenter is a quality-of-life policy, not a
  safety policy. If the augmenter is broken or the binary is
  missing, the text search still runs.

## What this file is not

- It is not a script. The runtime reads the policy description,
  not this directory's bytes.
- It is not a search replacement. The text search still runs;
  the augmenter only adds context.
- It is not a tool-specific extension. The policy stays
  runtime-agnostic; each target translates it. A future runtime
  that wants the same behaviour wires its own augmenter that
  reads this policy and resolves the binary in its own way.

## Reuse across runtimes

If a target cannot enforce the policy exactly as written (for
example, the runtime has no `PreToolUse` matcher for `Grep|Glob`,
or the runtime cannot shell out to a binary), the workaround
belongs in `targets/<tool>/hooks/` and must justify the
divergence in its first paragraph. Do not weaken the shared
policy to fit a single runtime.

A common divergence is **the resolution order**: a runtime that
manages MCP servers through a registry may resolve the binary
through its registry instead of through `$CODEBASE_MEMORY_MCP_BIN`.
The order above is the fallback for runtimes that do not have a
registry; the policy itself — "augment Grep/Glob with graph
context; never block" — is portable.

## Relationship to other assets

- MCP card: `assets/mcp-servers/codebase-memory-mcp.md`.
- Hook policy: `assets/hooks/codebase-memory-session-reminder.md`
  (the SessionStart counterpart that tells the agent the same
  thing once at the start of the session).
- Pack: `assets/packs/codebase-memory-assisted-workflow.md`.
