# Hook policy pattern: git push and PR preflight

> Shared hook assets are **policy notes**, not runtime wiring. This
> file is a lifecycle intent for a `PreToolUse` gate that runs
> against `Bash` invocations that would push a branch or open a
> pull request. See `assets/README.md` for the category contract.
> Executable hook scripts and runtime hook wiring live in
> `targets/<tool>/hooks/`.

## Lifecycle event

`PreToolUse` (matcher: `Bash`) — fires before the runtime
executes a shell command on the agent's behalf. The runtime
surfaces the command string, the structured input, and the session
context, and asks the policy whether to allow, deny, or modify the
invocation.

This pattern targets commands that match a push or PR-opening
shape. It runs only when the command resolves to a `git push`,
`gh pr create`, or equivalent; it does not run on every Bash
invocation.

## Policy

When the matched command is a push or PR-opening command, the
policy enforces the following preflight checks. The check order
is fixed: a missing or invalid prerequisite blocks the command
with exit code 2 and a short remediation hint.

1. **Remote is configured.** The target remote exists and is
   reachable. A missing remote is a hard fail.
2. **Working tree is clean.** No uncommitted changes, no
   untracked files outside `.gitignore`, and no in-progress merge
   or rebase. A dirty working tree is a hard fail for a push; a
   `--force` push is a hard fail in every case.
3. **Branch is up to date with the upstream tracking branch.**
   `git fetch` has run and the local branch is either equal to
   or ahead of its upstream. Behind upstream is a hard fail.
4. **Required checks are green.** CI on the most recent commit
   has finished, and the required status checks (as defined by
   the repository's branch protection) are all green. A pending
   or failing check is a hard fail.
5. **No blocked patterns in the diff.** The diff against the
   upstream branch does not introduce a path that the
   `boundary-respect` rule (`assets/rules/`) forbids pushing
   without explicit authorization (live sensitive config,
   `*.template`-protected files with values filled in, etc.).
6. **Authorization is present.** The current session has an
   explicit push authorization token or the user has typed an
   interactive confirmation in the most recent turn. No implicit
   authorization is accepted.

A clean preflight allows the command and records an audit entry.

## When the policy applies

- Applies to every `Bash` invocation that matches the push or
  PR-opening shape, on every runtime that supports a `PreToolUse`
  matcher for `Bash`.
- Applies to both interactive and non-interactive invocations.
- Does not apply to reads, listings, searches, or any other
  command shape. The matcher filters to the push/PR shape before
  the policy runs.

## What this file is not

- It is not a script. The runtime reads the policy description,
  not this directory's bytes.
- It is not a CI definition. CI runs on the server after a push;
  this gate runs before the push. The two layers are
  complementary, not redundant.
- It is not a tool-specific extension. The policy stays
  runtime-agnostic; each target translates it.

## Reuse across runtimes

If a target cannot enforce the policy exactly as written (for
example, the runtime has no `PreToolUse` matcher for `Bash`, or
the runtime cannot read the current session's authorization
context), the workaround belongs in `targets/<tool>/hooks/` and
must justify the divergence in its first paragraph. Do not weaken
the shared policy to fit a single runtime.

A common divergence is **CI status verification**: Claude Code's
hook shell can call `gh pr checks` or the equivalent; Codex may
have a different status API; oh-my-pi may need to shell out to
`gh` or `git`. The check itself — "required status checks are
green" — is portable.

## Relationship to other assets

- Rule: `assets/rules/example-boundary-respect.md` (the blocked
  patterns step).
- Rule: `assets/rules/no-shared-commands-prompts-tips.md` (do not
  let the gate push a runtime command into `assets/`).
- Pack: `assets/packs/agent-blueprint-distribution.md` (the
  `deployment-operator` role and the `code-implementer` role both
  rely on this gate to keep the blast radius honest).
