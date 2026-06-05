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
