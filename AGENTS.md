# Agent working rules

Repo-specific rules for Codex and generic agents operating in this repository.

## Read first

- `README.md` — purpose and layout.
- `CONTEXT.md` — architecture, area roles, and stability boundaries.

## Working rules

- Treat `assets/` as reusable configuration material; do not mix runtime artefacts into it.
- Treat `targets/` as a per-tool landing area. Each tool owns its subdirectory; do not assume its contents are stable.
- Put untriaged material in `inbox/`; retire things to `archive/` rather than deleting silently.
- Maintenance documentation (issue tracker, triage labels, domain conventions) lives under `docs/maintenance/`. It is not a configuration asset.
- This repo is a working stash, not a stable contract. Do not depend on path layout or file contents across tools.

## Where to find maintenance details

- `docs/maintenance/issue-tracker.md` — how issues and PRDs are tracked.
- `docs/maintenance/triage-labels.md` — triage label vocabulary.
- `docs/maintenance/domain.md` — how skills should consume domain docs.
