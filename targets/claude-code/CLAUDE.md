# Claude Code direct behavior entrypoint

Loaded by Claude Code when it operates against this landing area. Keep this
file focused on behavior Claude Code should follow when reading, writing, or
rewriting material under `targets/claude-code/`.

## Working rules

- Treat this directory as Claude Code's runtime landing area. Do not assume
  its contents are stable across runs; another Claude Code invocation may
  rewrite them.
- Read `targets/claude-code/README.md` for layout and boundary rules before
  adding or moving files.
- Runtime-native files (`agents/`, `commands/`, `skills/`, `hooks/`) belong
  here. Reusable material belongs in `assets/` at the repo root, not here.
- Configs likely to hold secrets, local paths, model routing, or
  machine-specific values must be shipped as `*.template` files. Do not
  commit a live `settings.json` or `mcp.json` with those values filled in.
- Hooks under `hooks/` use Claude Code's hook format. Do not generalize the
  format to other runtimes.

## When wiring MCP

- Start from `mcp.json.template`. Copy it to `mcp.json` locally and fill in
  transport, command, args, env, and any tokens.
- Do not commit the live `mcp.json`. The template is the only file that
  belongs in the repo.

## When wiring settings

- Start from `settings.json.template`. Copy it to `settings.json` locally
  and fill in model routing, permission scopes, and any machine-specific
  values.
- Do not commit the live `settings.json`.

## When commands or skills change

- Slash commands stay under `targets/claude-code/commands/`. Do not create a
  shared `commands/` directory at the repo root.
- Tool-local skill overrides stay under `targets/claude-code/skills/`. If a
  skill is reusable across runtimes, it belongs in `assets/skills/`.

## When hooks change

- Hook implementations stay under `targets/claude-code/hooks/`. The hook
  format is Claude Code-specific; do not assume Codex or oh-my-pi can load
  the same file.
