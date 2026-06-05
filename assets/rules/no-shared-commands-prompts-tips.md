# Rule: no shared `commands/`, `prompts/`, or `tips/` directories

This file is a **reusable behavioural rule** an agent should follow
when working in this repo. It complements
`assets/rules/example-boundary-respect.md` by pinning down the one
shape of "almost-promoted" material that must not become a shared
asset.

> See `assets/README.md` for the category contract. A rule is
> short, declarative, and runtime-agnostic. It is designed to be
> composed into a future `CLAUDE.md` or `AGENTS.md` without
> modification.

## Rule

Do not introduce a shared `commands/`, `prompts/`, or `tips/`
directory at any of these locations:

- the repo root,
- `assets/` (in any form, subdirectory or otherwise),
- `targets/<tool>/` as a sibling of the per-tool subdirectory.

A command, prompt, or tip is owned by a single runtime tool. The
runtime owns its own slash-command namespace, its own prompt
catalogue, and its own tip style. Shared shapes drift over time as
runtimes evolve at different speeds; a single shared shape becomes a
tax on every other tool that has to read it.

## What to do with material that looks like a command or prompt

- Slash commands (Claude Code `commands/*.md`): land in
  `targets/claude-code/commands/`. Keep them in the runtime's
  native shape; do not wrap them in a shared card.
- Codex prompts or instruction blocks: land in
  `targets/codex/`. The committed `config.toml.template` documents
  the contract.
- oh-my-pi extension prompts: land in
  `targets/oh-my-pi/extensions/<name>/`. Extensions own their
  prompt text; do not lift it into `assets/`.
- A genuinely reusable workflow, expressed as a sequence of agent
  decisions and tool calls, belongs in `assets/skills/` as an Agent
  Skills standard workflow, not as a command. See
  `assets/skills/example-repo-triage.md` for the shape.

## Why this rule exists

Issue #10 of this repo (Promote reusable Claude Code material into
shared assets) makes the rule explicit at the inventory level:

- The `commands/` category in `~/.claude/commands/*.md` is
  classified as **migrate** to `targets/claude-code/commands/`,
  *not* to `assets/`.
- The `prompts/` and `tips/` categories do not exist in this repo
  as a shared layer, and must not be invented.
- A pack under `assets/packs/` may *link* a runtime command by
  reference, but the command file itself stays in
  `targets/<tool>/commands/`.

## How to consume this rule

A future `CLAUDE.md` or `AGENTS.md` composes this file by reference
or by quoting the rule. The rule stays small and declarative so it
can be embedded in tool-specific behaviour entrypoints without
losing meaning.
