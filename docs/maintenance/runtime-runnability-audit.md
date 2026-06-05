# Runtime target runnability audit (issue #12)

Read-only decision record. This document classifies every committed
piece of material under `targets/claude-code/`, `targets/codex/`, and
`targets/oh-my-pi/` into one of five buckets, so readers can tell at a
glance what works out of the box, what must be filled in locally, what
is intentionally absent, what was deliberately skipped, and what is
blocked behind a missing prerequisite.

This slice does not modify any live runtime configuration. It audits
the committed material only.

## Bucket definitions

The five buckets, applied uniformly across the three targets:

- **runnable** — works on this repo as committed; no local filling
  required. The file is documentation, a pure helper, or a script that
  resolves its dependencies from the environment at run time.
- **template-only** — a sanitized shape with placeholder values. The
  file is reusable in shape but must be copied to its live filename
  (e.g. `settings.json`, `config.toml`, `omp.config.json`,
  `mcp.json`) and have the placeholders replaced on the target
  machine before the runtime can use it. The committed copy is **not**
  loaded by the runtime.
- **missing** — the runtime has a target directory in this repo, but
  the corresponding local runtime root is absent on this machine
  (e.g. Codex). No real source, hooks, agents, commands, or skills
  were ever committed; only the template and the boundary docs.
- **skipped** — live runtime state that must not be committed under
  any circumstance. Sessions, transcripts, caches, logs, local
  databases, secrets, install IDs, native binaries, plugin caches.
  See `docs/maintenance/runtime-config-inventory.md` for the full
  skip list.
- **blocked** — committed material that *looks* runnable but cannot
  work on a clean clone because it depends on a prerequisite that is
  not in this repo and not installed by the install scripts
  (external scripts, runtime-installed sibling binaries, marketplace
  plugins, etc.). The doc records the missing prerequisite so the
  reader knows what to install before the file can be used.

The five buckets are exhaustive for this repo. A file is exactly one
of the five; the bucket is decided by what the runtime would do with
the committed copy on a clean clone.

## Repository-level boundary check

| Concern                                                | Bucket          | Source of truth                          |
| ------------------------------------------------------ | --------------- | ---------------------------------------- |
| `settings.json`, `mcp.json`, `config.toml`, `omp.config.json` | **skipped** (no live copies) | `scripts/validate_repo_structure.py`     |
| `*.template` siblings of the above                     | **template-only** | Each target's template file             |
| Hook / extension implementations                       | **runnable** or **blocked** | Source files under `targets/<tool>/hooks/`, `targets/<tool>/extensions/` |
| Slash commands                                         | **runnable** or **blocked** | `targets/<tool>/commands/*.md`           |
| Agent definitions                                      | **runnable** or **blocked** (frontmatter-only `model`, `effort`, `permissionMode` are runnable; frontmatter `PreToolUse` hook commands that resolve to a non-repo install path are blocked) | `targets/<tool>/agents/*.md`             |
| Skills                                                 | empty in all three targets; reusable methodology lives in `assets/skills/` | `targets/<tool>/skills/.gitkeep`         |

The `scripts/validate_repo_structure.py` script confirms the top
boundary: no live `settings.json`, `mcp.json`, `config.toml`, or
`omp.config.json` is committed under any target. The structure check
is the structural guarantee behind the "no live runtime config
modified" clause of this audit.

## Claude Code — `targets/claude-code/`

| Path                                               | Bucket                | Prerequisite / why                                                                  |
| -------------------------------------------------- | --------------------- | ----------------------------------------------------------------------------------- |
| `README.md`, `CLAUDE.md`, `agents/README.md` (3 files)           | **runnable**          | Pure documentation. `README.md` is the target overview, `CLAUDE.md` is loaded by Claude Code when it enters the tree, and `agents/README.md` describes the agent set. None of the three is consumed as configuration. |
| `agents/code-implementer.md`, `agents/codebase-discovery.md`, `agents/deployment-operator.md`, `agents/mavis.md`, `agents/test-engineer.md` (5 files) | **runnable**          | Frontmatter carries `model`, `effort`, `permissionMode`. The model identifiers match the routing names already in `omp.config.json.template`, so they resolve on a clean clone if the runtime's `modelRoles` block is filled. No absolute paths in the agent bodies, and no frontmatter hooks requiring a non-repo install. |
| `agents/code-reviewer.md`                            | **blocked**           | Frontmatter `PreToolUse` (matcher: `Write`) hook command is `~/.claude/hooks/validate-agent-artifact-write/hook.mjs code-reviewer`. The bundle's own `README.md` (`targets/claude-code/hooks/validate-agent-artifact-write/README.md`) states the directory must be copied to `~/.claude/hooks/validate-agent-artifact-write/`; no auto-install. On a clean clone, the hook command does not exist and the agent cannot satisfy its frontmatter contract. |
| `agents/task-planner.md`                             | **blocked**           | Frontmatter `PreToolUse` (matcher: `Write`) hook command is `~/.claude/hooks/validate-agent-artifact-write/hook.mjs task-planner`. Same `validate-agent-artifact-write/` install prerequisite as `code-reviewer.md`; no auto-install from this repo. |
| `commands/agent-plan.md`                           | **runnable**          | Pure prompt body. Writes to `.agent-runs/plans/{plan_id}/` (repo-local).            |
| `commands/new-feature.md`                          | **blocked**           | Body invokes `~/.claude/scripts/instantiate-feature.sh` and reads template files from `~/.claude/baselines/durable-workflow-v1/baseline/docs/specs/_template/`. Neither the script nor the baseline cache is in this repo. The `~`-relative paths are expanded at runtime by Claude Code and resolve to the user's home directory, not the repo. A clean clone cannot satisfy these. |
| `hooks/git-push-pr-preflight.sh`                   | **runnable**          | Operates on the tool-input `cwd`; no env vars, no absolute paths.                   |
| `hooks/cbm-session-reminder`                       | **runnable**          | Prints a static reminder; no path resolution, no external calls.                   |
| `hooks/cbm-code-discovery-gate`                    | **blocked** (functional)**\*** | The script does not block, it only augments. It silently no-ops when `codebase-memory-mcp` is not installed (env var unset, default missing). Augmentation is therefore **blocked** until the binary is installed; the PreToolUse gate never blocks either way. |
| `hooks/agent-model-override-gate.py`               | **template-only**     | Reads the override file from `CLAUDE_AGENT_MODEL_OVERRIDE_SECRET_FILE` if set, otherwise a `Path.home()`-relative default. No absolute user path in the committed copy. The hook is wired to `PreToolUse` (matcher: `Agent`) and is loaded as a Claude Code hook once the `settings.json` is filled. |
| `hooks/validate-agent-artifact-write/hook.mjs`     | **runnable**          | Uses `process.env.TMPDIR` or `os.tmpdir()`. No absolute paths.                      |
| `hooks/validate-agent-artifact-write/scope.md` etc. | **runnable**         | Documentation, executable hook shape only.                                         |
| `mcp.json.template`                                | **template-only**     | `codebase-memory-mcp` `command` is `<absolute-path-to-codebase-memory-mcp-binary-on-this-machine>`. Must be filled in locally. |
| `settings.json.template` — env, model, permissions, hooks wiring | **template-only** | All placeholders (`<auth-token-or-env-reference>`, `<provider-base-url>`, `<absolute-path-to-agents-target-hooks>`, etc.) are described in the `_notes` block. Filling in the placeholders is the user's job. |
| `settings.json.template` — `statusLine`            | **template-only**     | The `command` is the local-placeholder token `<path-to-local-statusline-script-on-this-machine>`. The template ships no value Claude Code can run as-is; the user must either replace the placeholder with the absolute path of a statusline script they have installed locally, or remove the whole `statusLine` block to disable the statusline. The template's `_notes.statusLine` records this contract and points the user at this audit. The committed `hooks/` directory in this repo contains `agent-model-override-gate.py`, `git-push-pr-preflight.sh`, `cbm-code-discovery-gate`, `cbm-session-reminder`, and `validate-agent-artifact-write/` only; no statusline script is committed. The row is **template-only** because the only thing the template owns is the local-placeholder form of the command — the script itself is the user's prerequisite. |
| `settings.json.template` — `enabledPlugins`        | **template-only**     | Plugin IDs are real (`claude-md-management@claude-plugins-official`, `context7@…`, etc.) but the booleans reflect one machine's installed set. A clean clone has no plugins installed. Until each plugin is installed on the target machine, the entries are inert. |
| `settings.json.template` — `extraKnownMarketplaces` | **template-only**    | Marketplace URLs are placeholders. Until the marketplaces are added on the target machine, the entries are inert. |
| `settings.json.template` — `sandbox`, `language`, `theme`, `plansDirectory`, `skipDangerousModePermissionPrompt`, `teammateMode`, `hasCompletedOnboarding` | **template-only** | Local preference. Values are filled in by the user. |
| `skills/`                                           | **missing** (intentionally empty) | The target README records: "This target keeps no skill content of its own; `skills/` is empty by design until a Claude-Code-specific override is needed." Reusable skill methodology lives in `assets/skills/`. |

\* `cbm-code-discovery-gate` does not block; it silently no-ops when
the binary is missing. Calling it **blocked** is therefore an
overstatement of its gate effect, but the file as committed does
nothing useful without the binary installed, so the audit records it
as blocked on functionality (augmentation never happens) rather than
on enforcement (it never blocks either way).

## Codex — `targets/codex/`

The local Codex root is **absent on this machine** (`~/.codex/`,
`~/.config/codex/`, `~/.config/openai/`, and
`~/Library/Application Support/codex/` were each checked during the
issue #8 inventory and none exist). No real Codex configuration,
hooks, agents, commands, or skills are invented in this repo.

| Path                        | Bucket        | Prerequisite / why                                                       |
| --------------------------- | ------------- | ------------------------------------------------------------------------ |
| `README.md`                 | **runnable**  | Pure documentation.                                                      |
| `AGENTS.md`                 | **runnable**  | Pure documentation, loaded by Codex when it enters the tree.             |
| `config.toml.template`      | **template-only** | Sanitized shape. The committed copy is not loaded by Codex; the live `config.toml` does not exist on this machine. |
| `agents/`, `commands/`, `hooks/`, `skills/` | **missing** (intentionally empty) | No real Codex source migrated. The `.gitkeep` files document the shape; no content is committed. The target's README records the boundary. |

The classification for Codex is therefore uniformly **template-only
or missing** at this commit. The audit explicitly records the
**runtime source absence** so a reader does not assume the template
plugs into a populated runtime. When a Codex root later appears on
this machine, the issue #8 inventory classification should be
applied to it and the audit re-issued.

## oh-my-pi — `targets/oh-my-pi/`

| Path                                                           | Bucket                | Prerequisite / why                                                              |
| -------------------------------------------------------------- | --------------------- | ------------------------------------------------------------------------------- |
| `README.md`                                                    | **runnable**          | Pure documentation.                                                             |
| `omp.config.json.template`                                     | **template-only**     | All values are placeholders. The `providers` block is commented out by design; the live `omp.config.json` does not exist on this machine. |
| `extensions/codebase-memory-gate/index.ts`                     | **template-only**     | The extension is loaded by the harness only when the extension is registered in `omp.config.json` `extensions.load_paths`. The template's default load path is `targets/oh-my-pi/extensions`, which exists, but the harness will not load the extension until the live `omp.config.json` is filled in. The extension itself depends on `codebase-memory-mcp` being installed and accessible. |
| `extensions/codebase-memory-gate/classification-helpers.ts`   | **runnable**          | Pure helper, exported for tests. No runtime dependencies.                       |
| `extensions/codebase-memory-gate/tests/gate-classification.test.mjs` | **runnable**     | Pure unit test over `classification-helpers`. No env vars, no OMP spawn.        |
| `extensions/codebase-memory-gate/tests/behavior-smoke.test.mjs` | **runnable**          | Pure smoke test over `classification-helpers`. No env vars, no OMP spawn.       |
| `extensions/codebase-memory-gate/tests/e2e-smoke.test.mjs`    | **blocked**           | Reads `OMP_AGENT_DIR` from the environment. Spawns real OMP processes against a local OMP install and a local code fixture. Defaults are empty so a clean clone fails loudly. The test is **e2e-dependent**: it needs the runtime to be installed and the OMP agent directory to be set. |
| `extensions/codebase-memory-gate/tests/proxy-epipe.test.mjs`  | **blocked**           | Reads `CBM_PROXY_PATH` from the environment. The proxy itself (`codebase-memory-mcp-omp-proxy.mjs`) is intentionally **not** migrated into this target; it is a runtime-installed sibling at the agent root. The test will not run on a clean clone and `run-tests.sh` already skips it when `CBM_PROXY_PATH` is unset. |
| `extensions/codebase-memory-gate/tests/run-tests.sh`           | **runnable**          | Test runner. Runs unit tests when `bun` is available, e2e tests when `OMP_AGENT_DIR` is set, and skips proxy tests when `CBM_PROXY_PATH` is unset. The runner itself does not need a filled `omp.config.json` to launch. |
| `extensions/` (top-level, including `.gitkeep`)                | **runnable**          | Directory marker; the only committed content is `codebase-memory-gate/`.        |
| `skills/`                                                      | **missing** (intentionally empty) | The target README records: "Reusable skills stay in `assets/skills/`." The target's own `skills/` is empty by design. |

The audit's explicit recording of the **proxy/e2e dependencies** is
that:

- `proxy-epipe.test.mjs` depends on the `codebase-memory-mcp-omp-proxy.mjs`
  proxy, which is a runtime-installed sibling at the agent root
  (`~/.omp/agent/codebase-memory-mcp-omp-proxy.mjs`). It is
  intentionally **not** migrated into this target. To run the proxy
  test, set `CBM_PROXY_PATH` to the absolute path of the proxy on
  the target machine.
- `e2e-smoke.test.mjs` depends on the local OMP install. It reads
  the agent directory from `OMP_AGENT_DIR`. To run the e2e test, set
  `OMP_AGENT_DIR` to the absolute path of the OMP agent directory on
  the target machine.
- `run-tests.sh` already handles the no-prereq case by skipping the
  proxy tests when `CBM_PROXY_PATH` is unset. The e2e tests run by
  default and will fail loudly on a clean clone; that is intentional
  and recorded here.

## Aggregate counts

Counts are per logical row in the per-target tables above. A single
template file (e.g. `settings.json.template`) is split across rows
when different blocks of the same file have different buckets
(e.g. `statusLine` is template-only, `enabledPlugins` is template-only).
File-level counts are larger; row-level counts are what the
per-target tables record.

| Target          | runnable | template-only | missing | skipped (live state) | blocked |
| --------------- | -------: | ------------: | ------: | -------------------: | ------: |
| `claude-code`   |        7 |             7 |       1 |                    0 |       4 |
| `codex`         |        2 |             1 |       4 |                    0 |       0 |
| `oh-my-pi`      |        6 |             2 |       1 |                    0 |       2 |
| **Totals**      |   **15** |        **10** |   **6** |                **0** |   **6** |

These counts are the audit. They are derived from the per-target
tables above and from the committed file list under each target.

## What the audit does not cover

- `assets/` material is reusable across runtimes and is not part of
  this audit. Its bucket is uniformly **runnable** (documentation,
  policy notes, role blueprints).
- `inbox/` and `archive/` are empty at this commit. They are not
  targets and are out of scope.
- `docs/maintenance/` is documentation; it is uniformly **runnable**
  by construction (it is not consumed by any runtime as configuration).

## Downstream work implied by this audit

- The `statusLine` block in `settings.json.template` ships a
  local-placeholder command (`<path-to-local-statusline-script-on-this-machine>`).
  The template owns the placeholder form only; the script itself is
  the user's prerequisite. The user must either replace the
  placeholder with the absolute path of a statusline script they have
  installed locally, or remove the whole `statusLine` block to
  disable the statusline. No source change is implied; this audit
  records the truth.
- The `new-feature` slash command depends on `instantiate-feature.sh`
  and the `durable-workflow-v1` baseline cache. To make the command
  work, the user must install those files on the local machine. The
  command is **blocked** on a clean clone by design; no source change
  is implied.
- The `codebase-memory-gate` e2e and proxy tests are **blocked** on
  external runtime state. No source change is implied; the
  `run-tests.sh` script already handles the skip case.

## Re-issue conditions

This audit should be re-issued when:

- A new file is added under any target.
- A new external prerequisite is documented (e.g. a new marketplace
  plugin or a new runtime binary).
- A template comment is changed in a way that alters the
  "what the runtime will do with this" answer.
- Codex runtime source appears on this machine and Codex material
  is migrated.

The classification buckets in this document are the contract; the
per-target tables are the evidence.
