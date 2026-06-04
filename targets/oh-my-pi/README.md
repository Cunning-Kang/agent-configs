# oh-my-pi target

Runtime landing area for oh-my-pi. This directory is owned by oh-my-pi; its
contents may be rewritten by the tool at any time and are not a stable
contract. See `CONTEXT.md` at the repo root for the area role.

## What oh-my-pi is in this repo

oh-my-pi is **not a plain peer agent** in this repo. It is the harness and
entrypoint that orchestrates and inherits configuration for the other
runtimes (Claude Code, Codex, and any other agents wired into the same
harness). Treat it as the orchestrating layer; treat the other targets as
its delegates.

### Inheritance and orchestration behavior

- oh-my-pi loads its own config and extensions first, then may inherit or
  compose configuration from other runtime targets in this tree.
- oh-my-pi is the place to register the chain of agents, the skill set the
  harness exposes, and the orchestration policy that ties the runtimes
  together. Peer runtime targets (Claude Code, Codex) own their own
  runtime-native files; oh-my-pi owns the cross-runtime wiring.
- When a change affects more than one runtime, the orchestrating decision
  lives here, in `targets/oh-my-pi/extensions/` or in the harness config.
  Runtime-specific implementations stay in the relevant runtime target.

## Layout

| Path                    | Role                                                                |
| ----------------------- | ------------------------------------------------------------------- |
| `omp.config.json.template` | Template for the oh-my-pi harness config. Copy to `omp.config.json` to use. |
| `extensions/`           | Extension implementations loaded by oh-my-pi in its own format.    |
| `skills/`               | Target-specific skills the harness exposes. Reusable skills stay in `assets/skills/`. |

## Boundaries

- `extensions/` uses oh-my-pi's extension format. Do not assume the same
  format works for Claude Code or Codex hooks; those runtimes have their
  own hook areas under their own targets. Hook/extension implementations
  are intentionally not portable across runtimes.
- `omp.config.json.template` is a template only. Do not commit a live
  `omp.config.json` with secrets, absolute local paths, model routing, or
  machine-specific values. Copy the template and fill it in locally.
- The harness can register and orchestrate the other runtimes, but the
  runtime-specific files for Claude Code and Codex still live in
  `targets/claude-code/` and `targets/codex/`. Do not duplicate
  runtime-native files here.

## How to land a change here

1. Drop runtime-native files into the matching subdirectory.
2. If the file holds secrets, local paths, model routing, or machine-specific
   values, use the `*.template` filename and document the copy step.
3. Do not promote material from `targets/oh-my-pi/` into `assets/`. If the
   material is reusable across runtimes, it belongs in `assets/` from the
   start, not retrofitted here.
4. If the change is purely runtime-specific to Claude Code or Codex, do
   not place it here; place it in the matching runtime target.
