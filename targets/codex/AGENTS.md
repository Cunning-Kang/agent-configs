# Codex direct behavior entrypoint

Loaded by Codex when it operates against this landing area. Keep this file
focused on behavior Codex should follow when reading, writing, or rewriting
material under `targets/codex/`.

## Working rules

- Treat this directory as Codex's runtime landing area. Do not assume its
  contents are stable across runs; another Codex invocation may rewrite
  them.
- Read `targets/codex/README.md` for layout and boundary rules before
  adding or moving files.
- Runtime-native files (`agents/`, `commands/`, `hooks/`, `skills/`) belong
  here. Reusable material belongs in `assets/` at the repo root, not here.
- Configs likely to hold secrets, local paths, model routing, or
  machine-specific values must be shipped as `*.template` files. Do not
  commit a live `config.toml` with those values filled in.
- Hooks under `hooks/` use Codex's hook format. Do not generalize the
  format to other runtimes.

## When configuring Codex

- Start from `config.toml.template`. Copy it to `config.toml` locally and
  fill in model routing, providers, and any machine-specific values.
- Do not commit the live `config.toml`. The template is the only file that
  belongs in the repo.

## When commands or skills change

- Slash commands stay under `targets/codex/commands/`. Do not create a
  shared `commands/` directory at the repo root.
- Tool-local skill overrides stay under `targets/codex/skills/`. If a skill
  is reusable across runtimes, it belongs in `assets/skills/`.

## When hooks change

- Hook implementations stay under `targets/codex/hooks/`. The hook format
  is Codex-specific; do not assume Claude Code or oh-my-pi can load the
  same file.
