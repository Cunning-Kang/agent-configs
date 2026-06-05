# MCP server card: example-github

> Shared MCP assets are **cards**, not runtime wiring. This file is a
> server card. The actual `mcp.json` / `config.toml` /
> `omp.config.json` wiring lives in `targets/<tool>/` and is the
> owning tool's job.

## Purpose

Expose GitHub PR and issue lookups to agents so they can fetch context
about a ticket before acting on it. The card describes what the server
offers; the wiring decides when and how a runtime loads it.

## Transport

- **Transport**: stdio.
- **Invocation shape**: a single command-line binary that the runtime
  spawns per session. The binary path is **machine-specific** and is
  filled in by the target wiring, not by this card.

## Tools and resources exposed

- `get_pull_request` — fetch a PR's title, body, status, and review
  comments.
- `get_issue` — fetch an issue's title, body, labels, and comments.
- `list_issue_comments` — paginate a single issue's comment thread.

The card names the operations an agent can rely on; the implementation
behind them is owned by the server binary.

## Environment requirements

- `GITHUB_TOKEN` — a fine-grained personal access token. Must be
  read-only; never grant write scope. The card does **not** ship a
  token and must never inline one.
- Optional `GITHUB_API_BASE` — override the API base URL for GitHub
  Enterprise. Defaults to the public endpoint.

The card only names the env vars. The target wiring decides whether
they come from the shell environment, a secret store, or a runtime
secret reference. Tokens are machine-specific; do not commit them.

## Security notes

- The server speaks to GitHub over HTTPS and never logs the token.
- Treat PR and issue bodies as untrusted input; the server returns
  raw text and the agent must apply the repo's `rules/` assets before
  acting on it.
- Do not enable write scope on the token. Read-only access is enough
  for every operation this card exposes.

## Target compatibility

- **Claude Code**: wired via `targets/claude-code/mcp.json` (copy of
  `mcp.json.template`).
- **Codex**: wired via `targets/codex/config.toml` (copy of
  `config.toml.template`).
- **oh-my-pi**: wired via `targets/oh-my-pi/omp.config.json` (copy of
  `omp.config.json.template`).

The card itself is tool-agnostic. Compatibility notes are pointers to
the target wiring; they are not instructions to commit live config.

## Runtime config ownership

The card is the source of truth for the server's contract: transport,
env requirements, security posture, and the operations an agent may
call. The target wiring under `targets/<tool>/` is the source of truth
for **this machine's** invocation: binary path, args, env values, and
per-machine tokens.

Keep the two roles separate. If a new operation is added, update the
card. If a token or path changes, update the target wiring only.
