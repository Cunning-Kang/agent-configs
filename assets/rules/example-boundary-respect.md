# Example: reusable behavioural rule

This file is a minimal example of a **reusable behavioural rule** that
an agent should follow when working in this repo. Rules are short,
declarative, and runtime-agnostic. They are designed to be composed
into a future `CLAUDE.md` or `AGENTS.md` without modification.

> See `assets/README.md` for the category contract. Rules are not
> tool configuration; they are constraints on agent behaviour in this
> repo. A tool that loads rules does so by reference, not by copying.

## Rule: respect the area boundaries

When adding, moving, or rewriting material in this repo, place it in
the right area on the first try:

- Reusable material goes under `assets/<category>/` where
  `<category>` is one of `skills`, `agents`, `mcp-servers`, `hooks`,
  `rules`, `packs`. Anything else under `assets/` is a regression.
- Runtime-native material goes under `targets/<tool>/`. Each tool
  owns its subdirectory and may rewrite it. Do not put runtime
  material at the repo root or under `assets/`.
- Untriaged material goes to `inbox/`. Promotion out of `inbox/` is
  a deliberate decision, not a side effect of a write.
- Retired material goes to `archive/`. Do not delete silently.
- Maintenance documentation goes under `docs/maintenance/`. It is
  not configuration; it is not loaded by any runtime.

## Rule: never commit live sensitive config

The following files hold machine-specific values and MUST NOT be
committed:

- `targets/claude-code/settings.json`
- `targets/claude-code/mcp.json`
- `targets/codex/config.toml`
- `targets/oh-my-pi/omp.config.json`

Ship the `*.template` variant instead. Copy the template locally,
fill in the values, and keep the live file out of version control.

## Rule: keep the asset shape

Within `assets/`, respect the agreed file shape for each category:

- `assets/mcp-servers/` contains server **cards** (`.md` only). No
  `.json` / `.toml` / `.yaml` / `.yml` wiring.
- `assets/hooks/` contains policy **notes** (`.md` only). No
  executable scripts.
- `assets/agents/` contains role **blueprints** (`.md`). No
  runtime-native subagent definitions.
- `assets/packs/` contains composition **notes** (`.md`). Packs
  link to existing assets; they never copy or inline them.

## Rule: when in doubt, do not invent a category

If a new piece of material does not fit any existing
`assets/<category>/`, do not create a new top-level category on the
fly. Put the material in `inbox/`, then propose the new category in
an issue. The set of categories is the asset catalog and changes
deliberately.

## How to consume this rule

A future `CLAUDE.md` or `AGENTS.md` composes this file by reference
or by quoting the rules. The rules stay small and declarative so
they can be embedded in tool-specific behaviour entrypoints without
losing meaning.
