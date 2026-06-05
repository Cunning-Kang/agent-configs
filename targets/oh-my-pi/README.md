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

| Path                                       | Role                                                                                       |
| ------------------------------------------ | ------------------------------------------------------------------------------------------ |
| `omp.config.json.template`                 | Template for the oh-my-pi harness config. Copy to `omp.config.json` to use.                |
| `extensions/`                              | Extension implementations loaded by oh-my-pi in its own format.                            |
| `extensions/codebase-memory-gate/`         | Gate extension that forces code-discovery through codebase-memory-mcp (migrated, see below).|
| `skills/`                                  | Target-specific skills the harness exposes. Reusable skills stay in `assets/skills/`.      |

### `omp.config.json.template` shape

The template mirrors the shape of the local runtime config (`config.yml`
and `models.yml` in `~/.omp/agent/`) and folds in the harness-level
runtime, inheritance, orchestration, and extension wiring. The block
list is the source of truth for the harness contract:

- `modelRoles`, `defaultThinkingLevel`, `providers` — model routing and
  provider credentials. Machine-specific; placeholders only.
- `startup`, `retry`, `compaction`, `steeringMode`, `interruptMode`,
  `display`, `task`, `terminal`, `theme`, `tools`, `mcp`, `secrets`,
  `marketplace`, `dev` — harness policy. Local choices; placeholders or
  documented defaults.
- `extensions.load_paths` — repo-relative paths to load. The committed
  default is `targets/oh-my-pi/extensions`; replace per machine.
- `runtimes`, `inheritance`, `orchestration` — cross-runtime wiring
  owned by the harness. Keep these here even when runtimes change.

The committed template is the sanitized shape; values are placeholders.
Never commit a live `omp.config.json` with `apiKey`, `baseUrl`,
absolute paths, or any other machine-specific value.

### `extensions/codebase-memory-gate/`

Migrated from `~/.omp/agent/extensions/codebase-memory-gate/`. It is a
real extension implementation that intercepts code-discovery tool calls
(`read`, `search`, `find`, `ast_grep`) and blocks them unless the agent
has already used a `mcp__codebase_memory_mcp_*` tool first. Layout:

```
extensions/codebase-memory-gate/
├── index.ts                  # Gate extension entry point
├── classification-helpers.ts # Shared classification logic (exported for tests)
└── tests/
    ├── gate-classification.test.mjs
    ├── behavior-smoke.test.mjs
    ├── e2e-smoke.test.mjs
    ├── proxy-epipe.test.mjs
    └── run-tests.sh
```

The e2e and proxy test suites depend on a runtime-installed proxy
(`codebase-memory-mcp-omp-proxy.mjs`) that lives at the runtime root
(`~/.omp/agent/`) and is intentionally **not** migrated here. See
`docs/maintenance/runtime-config-inventory.md` for the classification
rationale. The committed tests read the proxy path and the e2e fixture
paths from environment variables (see the test files); a clean clone
runs the unit tests out of the box and skips the e2e/proxy tests until
the env vars are set.

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
- Runtime state (sessions, terminal-sessions, `*.db*`, logs, caches,
  natives, install-id, histories) and machine-local installs
  (`codebase-memory-mcp-omp-proxy.mjs`, the `.omp/agent/*.db*` files,
  `~/.omp/natives/`, etc.) are not migrated into this target. See
  `docs/maintenance/runtime-config-inventory.md` for the full
  classification; only the reusable, config-shaped material belongs
  under `targets/oh-my-pi/`.

## How to land a change here

1. Drop runtime-native files into the matching subdirectory.
2. If the file holds secrets, local paths, model routing, or machine-specific
   values, use the `*.template` filename and document the copy step.
3. Do not promote material from `targets/oh-my-pi/` into `assets/`. If the
   material is reusable across runtimes, it belongs in `assets/` from the
   start, not retrofitted here.
4. If the change is purely runtime-specific to Claude Code or Codex, do
   not place it here; place it in the matching runtime target.
5. If the material is live runtime state (sessions, logs, caches, native
   binaries, install ids, local databases, audit logs), do not commit it
   under any circumstance; skip-classified paths stay on the machine.
