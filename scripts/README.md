# `scripts/`

Local helper scripts for the `agent-configs` repository. The directory
holds the structure validator (closed in issue #5) and the install
helpers added in issue #6. Nothing here is a public API; the scripts
exist to make the agreed-on boundaries mechanical to enforce.

## Validation

```
python3 scripts/validate_repo_structure.py
```

Enforces the boundaries recorded in `CONTEXT.md` and `assets/README.md`:
top-level areas exist, `assets/` contains only the agreed reusable
categories, shared `commands/`, `prompts/`, `tips/` asset directories
never appear, each runtime target landing area exposes the expected
template config file and does not commit a live sensitive config file,
and the shared MCP and hook asset areas stay card/markdown-only.

Focused tests:

```
python3 -m unittest scripts.test_validate_repo_structure -v
```

## Install helpers (issue #6)

Three thin scripts automate the mechanical copy or link of a tool's
landing area from this repo into a user-controlled destination. They
are deliberately narrow: they will not become a profile manager, a
rollback system, a remote sync tool, or a sensitive config merger.

| Script | Source landing area | Default destination | Protected live config |
| ------ | ------------------- | ------------------- | --------------------- |
| `install_claude_code.py` | `targets/claude-code/` | `~/.claude` | `settings.json`, `mcp.json` |
| `install_codex.py` | `targets/codex/` | `~/.codex` | `config.toml` |
| `install_omp.py` | `targets/oh-my-pi/` | `~/.omp` | `omp.config.json` |

### Common usage

```
# 1. Plan only — does not touch the destination.
python3 scripts/install_claude_code.py

# 2. Apply the plan, copying files into the destination.
python3 scripts/install_claude_code.py --apply

# 3. Symlink each file instead of copying.
python3 scripts/install_claude_code.py --apply --link

# 4. Stage the templates next to an existing live config without
#    overwriting the live file. Off by default; the live file is
#    always preserved.
python3 scripts/install_claude_code.py --apply --include-live-config
```

The same flags work for `install_codex.py` and `install_omp.py`. The
source landing area and the default destination change per script;
see the table above.

### What the scripts do

* Walk the source landing area (e.g. `targets/claude-code/`) and
  classify every file.
* Copy or symlink each file into the destination, creating parent
  directories as needed.
* Rotate any file that would be overwritten to a backup
  (`README.md` -> `README.md.bak`, then `README.md.bak.1`, and so on)
  before writing the new content. The `--backup-suffix` flag
  controls the suffix used.
* Refuse to overwrite a live config file (e.g. `settings.json`) by
  default. Re-run with `--include-live-config` to stage the matching
  template next to the live file as `<name>.template` so the user
  can compare; the live file itself is never touched.
* Skip paths whose name or any segment matches a known live runtime
  state token (`secrets`, `cache`, `logs`, `history`, `sessions`,
  `database`, `db`, `keyring`, `credentials`, `tokens`, `storage`,
  `cookies`, `state`, `runtime`).
* Skip dotfiles/dotdirs that the engine does not explicitly
  recognise (`.ssh`, `.env`, `.aws`, etc.) and repo-internal files
  (`.gitkeep`, `.gitignore`, `.ds_store`, `thumbs.db`).
* Print the plan to stdout, the skip/refuse summary to stderr, and
  a final `copied=N linked=N backed_up=N skipped=N refused=N`
  summary line in non-dry-run mode.

### What the scripts intentionally refuse to do

* **No profile manager.** The scripts do not track which files came
  from this repo and which are user-owned. A subsequent run will
  treat every existing destination file as user content and rotate it
  to a backup rather than overwriting it.
* **No rollback system.** Backups are simple rotated copies next to
  the original. The scripts do not maintain a history, do not let
  you "undo" a prior install, and do not garbage-collect old
  backups.
* **No remote sync tool.** There is no `git pull`, no remote
  fetching, no network call. The scripts read the local source
  tree, nothing more.
* **No sensitive config merger.** A live config file at the
  destination is never merged, edited, or replaced. The only
  interaction with live config is the refusal to touch it; the
  `--include-live-config` flag stages the template beside it for
  manual diffing. The user owns the merge.
* **No automatic secret injection.** The scripts do not read
  environment variables, do not interpolate tokens into templates,
  and do not move files into or out of `secrets/`, `tokens/`, or
  any other runtime state directory.
* **No silent overwrite.** Every mutation is preceded by a backup
  rotation; every backup rotation is announced on stdout as a
  `BAK    <path>` line before it happens.
* **No surprise hooks/permission changes.** Hooks are copied
  verbatim from the source. The scripts do not enable hooks in any
  live config and do not alter `permissions.allow` /
  `permissions.deny`. If the destination has live `permissions`
  fields, those fields are preserved.

### Focused tests

```
python3 -m unittest scripts.test_install_helpers -v
```

The test suite builds small, in-memory source trees that mirror the
real `targets/<tool>/` landing areas and exercises the engine and
each per-tool CLI end-to-end. Behaviour covered:

* Dry-run reports the plan and does not mutate the destination.
* Copy mode copies files; link mode symlinks them.
* Overwritten files are rotated to a backup before being replaced,
  and the numeric tail is incremented if a previous backup exists.
* Skip tokens (`secrets`, `cache`, `history`, etc.) and dotdirs are
  recorded as `SKIP` actions.
* Live config files are refused by default and staged as
  `<name>.template` only with `--include-live-config`.
* Each per-tool CLI lists its protected live config filenames via
  `--list-live-config`.

## Live-config exporter (issue #15)

A read-only counterpart to the install helpers. The exporter reads
the local oh-my-pi `config.yml` and `models.yml`, projects them into
the shape of the committed `omp.config.json.template`, and replaces
every machine-specific value with a placeholder. Sessions, terminal
sessions, logs, caches, `*.db*` files, `natives/`, install IDs,
histories, audit logs, and the runtime proxy are never read or
copied into the output; the exporter refuses any input path whose
name or any segment names live runtime state.

| Script | Source | Default input | Default output |
| ------ | ------ | ------------- | -------------- |
| `export_omp_config.py` | `scripts/omp_config_exporter/` | `~/.omp/agent/config.yml` + `~/.omp/agent/models.yml` | `targets/oh-my-pi/omp.config.json.template` |

### Common usage

```
# 1. Dry-run: print the plan, redaction summary, and redaction
#    count. Nothing is written to disk.
python3 scripts/export_omp_config.py

# 2. Apply the plan, writing the sanitized template over the
#    committed artifact.
python3 scripts/export_omp_config.py --apply --force

# 3. Point the exporter at non-default input paths (handy for
#    tests and CI). Output is also configurable.
python3 scripts/export_omp_config.py \
    --config /path/to/config.yml \
    --models /path/to/models.yml \
    --output /tmp/omp.config.json.template

# 4. Models-only export when the live config is unavailable.
python3 scripts/export_omp_config.py --allow-missing-config

# 5. Fail loudly when the live models file is missing. The
#    exporter records a REFUSE on the plan and continues
#    producing a template; passing --apply together with a
#    refused input makes the run exit non-zero (status 4) and
#    leaves --output untouched so a partial export never lands
#    on disk.
python3 scripts/export_omp_config.py --require-models
```

### What the exporter does

* Reads `config.yml` and `models.yml` with a small, stdlib-only
  YAML loader that accepts the block-style subset the OMP runtime
  emits (block mappings, sequences of scalars, and the
  `models: - id: Opus / name: Opus` inline-mapping sequence style).
* Redacts provider credentials (`apiKey`), base URLs, model
  identifiers, theme names, thinking levels, and absolute
  extension paths to placeholders. Provider ids in
  `providers.<id>` are folded into a single `<provider-id>` key
  so the committed template shows the shape without naming a
  specific provider.
* Passes through policy fields that are not machine-specific
  (`retry`, `compaction`, `skills`, `startup`, `display`, etc.)
  so the produced template is a drop-in replacement for the
  committed one.
* Renders a plan and a `REDACT` line listing the per-category
  redaction count (`api_keys`, `base_urls`, `model_ids`,
  `absolute_paths`, etc.) on stdout. A dry-run summary line at
  the end (`redactions=N refused_inputs=M`) is suitable for
  CI grep.
* Refuses to overwrite an existing `--output` file unless
  `--force` is passed. The committed template is the default
  destination; the safety check is the same shape the install
  helpers use.
* Refuses to write a partial export: `--apply` together with a
  plan that has any refused input exits non-zero (status 4) and
  leaves `--output` untouched. Dry-run still emits the plan so
  the user can see the refusal and decide what to do next.

### What the exporter intentionally refuses to do

* **No live runtime state is read.** Any path whose name matches
  `agent.db`, `history.db`, `models.db`, `autoqa.db`, the
  `codebase-memory-mcp-omp-proxy.mjs` runtime proxy, or whose
  segments include `sessions`, `terminal-sessions`, `cache`,
  `logs`, `history`, `audit`, `natives`, `install-id`, `state`,
  or `runtime` is recorded as a `REFUSE` on the plan. The
  exporter never opens the file.
* **No automatic overwrite of the committed template.** The
  exporter refuses to clobber an existing `--output` unless
  `--force` is passed. The user owns the diff.
* **No secret-shaped passthrough.** Each passthrough block in
  `config.yml` is filtered through a closed schema whitelist
  that mirrors the keys the committed
  `omp.config.json.template` documents as machine-neutral.
  Unknown keys are dropped (counted under
  `unknown_passthrough_dropped` on the REDACT line), and every
  scalar that survives the whitelist is deep-scanned for
  secret-shaped patterns (`sk-`, `https?://`, `/Users/`,
  `~/.omp`, `postgres`/`mysql` connection strings, `agent.db`,
  `session`, `cache`, `log`, `history`). Anything that matches
  is replaced with `<redacted>` rather than copied through.
* **No partial-export write on refuse.** `--apply` together with
  a plan that has any refused input exits non-zero (status 4)
  and leaves `--output` untouched. Dry-run still emits the plan
  so the user can see the refusal and decide what to do next.
* **No remote calls.** The exporter reads the local input paths
  and writes (on `--apply`) to the local output path. No
  network, no environment-variable injection, no shell out.
* **No third-party dependencies.** The stdlib is enough; the
  YAML loader is a hand-rolled, narrow subset parser.

### Focused tests

```
python3 -m unittest scripts.test_omp_config_exporter -v
```

The test suite builds small, in-memory input trees that mirror
the shape of the live OMP `config.yml` and `models.yml`, then
exercises the engine and the CLI end-to-end. Behaviour covered:

* YAML loader parses block-style mappings, sequences of scalars,
  and inline-mapping sequence items.
* Redaction swaps credentials, base URLs, model identifiers,
  theme names, thinking levels, extension paths, and per-provider
  blocks with placeholders. Multi-provider inputs are emitted
  with unique placeholder keys (`<provider-id>`, `<provider-id-2>`,
  ...) so no provider silently clobbers another.
* Per-block schema whitelists drop unknown passthrough keys and
  bump an `unknown_passthrough_dropped` counter; a deep scan
  replaces any surviving scalar that looks like a secret
  (`sk-`, `https?://`, `/Users/`, `~/.omp`, `postgres`/`mysql`
  connection strings, `agent.db`, `session`, `cache`, `log`,
  `history`) with `<redacted>`.
* Missing files produce a plan with a `REFUSE` rather than
  crashing; runtime-state token paths are refused up front, even
  when passed as a direct argument. `--apply` together with a
  refused input exits non-zero (status 4) and leaves `--output`
  untouched.
* Dry-run is the default; `--apply` writes the produced template;
  `--force` overwrites an existing output; without `--force` the
  exporter refuses to clobber the committed template.
* The redaction summary is rendered on the plan and is sufficient
  to verify that every live value has been redacted.