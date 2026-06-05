# Hook policy pattern: codebase-memory session reminder

> Shared hook assets are **policy notes**, not runtime wiring. This
> file is a lifecycle intent for a `SessionStart` reminder that
> tells the agent to use the codebase-memory-mcp tools first for
> any code exploration. See `assets/README.md` for the category
> contract. Executable hook scripts and runtime hook wiring live in
> `targets/<tool>/hooks/`.

## Lifecycle event

`SessionStart` (matcher: `startup|resume|clear|compact`) — fires
when the runtime starts a new session, resumes an existing
session, clears context, or compacts it. The runtime surfaces the
matcher name and the session context, and asks the policy for any
reminder text to inject into the new session.

This pattern is a **one-shot reminder**, not a gate. It prints a
short, static block of advice at the start of the session and
exits 0.

## Policy

When the matcher fires, the reminder prints a block that names the
codebase-memory-mcp tools the agent should reach for first, in
this order, for any code exploration:

1. `search_graph` — find nodes by name pattern, label, or
   question pattern.
2. `trace_path` — follow call chains, data flow, or cross-service
   links starting from a symbol.
3. `get_code_snippet` — fetch the exact source of a symbol at
   precise ranges.
4. `query_graph` — run an arbitrary Cypher query against the
   graph.
5. `get_architecture` — return a structured map of the
   repository's architecture for the requested aspects.
6. `search_code` — graph-augmented text search; preferred over
   raw `ripgrep` for code questions.

The reminder then notes that `Grep` / `Glob` / `Read` are still
free to use for text, configs, non-code files, and as a
fallback; that the agent should always read a file before editing
it; and that an unindexed project should be indexed with
`index_repository` first.

The reminder is **static** in this repo. It does not call the
codebase-memory-mcp binary. If a future revision of the reminder
needs to call the binary (for example, to print a one-line
"indexed projects" summary), the call must resolve the binary from
`$CODEBASE_MEMORY_MCP_BIN` with a documented placeholder default;
the committed source must never hard-code an absolute user path.

## When the policy applies

- Applies to every `SessionStart` event, on every runtime that
  supports a `SessionStart` matcher (Claude Code today; a future
  runtime that exposes the same matcher can adopt the same
  policy unchanged).
- Applies to startup, resume, clear, and compact. All four
  matchers fire the same reminder.
- Does not apply to other lifecycle events. The PreToolUse
  counterpart is a separate policy
  (`assets/hooks/codebase-memory-search-augment.md`).

## What this file is not

- It is not a script. The runtime reads the policy description,
  not this directory's bytes.
- It is not a per-request augmenter. The reminder fires once per
  session start, not per tool call. Per-tool augmentation is the
  PreToolUse policy.
- It is not a tool-specific extension. The policy stays
  runtime-agnostic; each target translates it.

## Reuse across runtimes

If a target cannot enforce the policy exactly as written (for
example, the runtime has no `SessionStart` hook, or the runtime
cannot inject text into a new session), the workaround belongs
in `targets/<tool>/hooks/` and must justify the divergence in its
first paragraph. Do not weaken the shared policy to fit a single
runtime.

A common divergence is **the matcher set**: some runtimes may not
distinguish `startup` / `resume` / `clear` / `compact`; in that
case the runtime fires the reminder on every session boundary,
which is a safe over-approximation.

## Relationship to other assets

- MCP card: `assets/mcp-servers/codebase-memory-mcp.md`.
- Hook policy: `assets/hooks/codebase-memory-search-augment.md`
  (the per-search counterpart).
- Pack: `assets/packs/codebase-memory-assisted-workflow.md`.
