#!/usr/bin/env python3
"""Repository structure and safety-boundary validator.

Enforces the architecture agreed in `CONTEXT.md`, `assets/README.md`, and the
target READMEs without relying on manual review. Each rule names the
architectural boundary it guards, so a failure points directly at what
regressed.

Boundaries enforced:

  * Top-level architecture areas exist
    (`assets/`, `targets/`, `scripts/`, `inbox/`, `archive/`,
    `docs/maintenance/`).
  * `assets/` contains only the agreed reusable categories
    (`skills/`, `agents/`, `mcp-servers/`, `hooks/`, `rules/`, `packs/`).
  * Shared `commands/`, `prompts/`, `tips/` asset directories never appear
    under `assets/`.
  * Each runtime target landing area exposes its expected template config
    file and does not commit a live sensitive config file
    (`settings.json`, `mcp.json`, `config.toml`, `omp.config.json`).
  * `assets/mcp-servers/` contains only server cards; no runtime-native
    config snippets (`.json` / `.toml` / `.yaml` / `.yml`).
  * `assets/hooks/` contains only policy notes (`.md`); no executable
    hook scripts.

Exit code: 0 on success, 1 on any boundary failure. All failures are
listed together so a single run surfaces every regression.

Usage:

    python3 scripts/validate_repo_structure.py
    python3 scripts/validate_repo_structure.py --root /path/to/repo
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# --- Boundary definitions -----------------------------------------------------

# Top-level architecture areas. The order matches `CONTEXT.md`'s area table.
REQUIRED_TOP_LEVEL_AREAS: tuple[str, ...] = (
    "assets",
    "targets",
    "scripts",
    "inbox",
    "archive",
    "docs",
)

# `docs/` itself is required, and so is its maintenance subtree.
REQUIRED_MAINTENANCE_AREAS: tuple[str, ...] = (
    "docs/maintenance",
)

# Agreed reusable asset categories per `assets/README.md`. Anything else
# directly under `assets/` is a regression against the catalog.
ALLOWED_ASSET_CATEGORIES: frozenset[str] = frozenset(
    {"skills", "agents", "mcp-servers", "hooks", "rules", "packs"}
)

# Shared `commands/`, `prompts/`, `tips/` directories are explicitly out of
# scope for the reusable asset area. They are also forbidden anywhere else
# directly under `assets/` (e.g. an accidental `assets/commands/foo.md`).
FORBIDDEN_ASSET_SUBDIRS: frozenset[str] = frozenset(
    {"commands", "prompts", "tips"}
)

# Per-target expected template files (machine-specific config) and the
# live sensitive config files that MUST NOT be committed.
TARGET_TEMPLATES: dict[str, dict[str, tuple[str, ...]]] = {
    "claude-code": {
        "templates": ("settings.json.template", "mcp.json.template"),
        "forbidden_live": ("settings.json", "mcp.json"),
    },
    "codex": {
        "templates": ("config.toml.template",),
        "forbidden_live": ("config.toml",),
    },
    "oh-my-pi": {
        "templates": ("omp.config.json.template",),
        "forbidden_live": ("omp.config.json",),
    },
}

# Runtime-native config extensions. Allowed in `targets/`, forbidden under
# `assets/mcp-servers/`. We deliberately do not allow these formats in
# shared MCP assets: per the catalog, those are cards, not wiring.
RUNTIME_CONFIG_EXTENSIONS: frozenset[str] = frozenset(
    {".json", ".toml", ".yaml", ".yml"}
)

# --- Failure model ------------------------------------------------------------


@dataclass(frozen=True)
class Failure:
    """A single architectural-boundary violation."""

    boundary: str
    detail: str


def _rel(root: Path, path: Path) -> str:
    """Display a path relative to the repo root, or absolute as a fallback."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


# --- Check functions ----------------------------------------------------------


def check_top_level(root: Path) -> list[Failure]:
    """Top-level architecture areas must all exist."""
    failures: list[Failure] = []
    for area in REQUIRED_TOP_LEVEL_AREAS:
        path = root / area
        if not path.is_dir():
            failures.append(
                Failure(
                    boundary="top-level area",
                    detail=f"missing required area: {_rel(root, path)}",
                )
            )
    for area in REQUIRED_MAINTENANCE_AREAS:
        path = root / area
        if not path.is_dir():
            failures.append(
                Failure(
                    boundary="maintenance area",
                    detail=f"missing required area: {_rel(root, path)}",
                )
            )
    return failures


def _iter_immediate_subdirs(path: Path) -> Iterable[Path]:
    """Yield direct subdirectories, ignoring dotfiles like `.gitkeep`."""
    if not path.is_dir():
        return
    for child in sorted(path.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            yield child


def check_asset_categories(root: Path) -> list[Failure]:
    """`assets/` must contain only the agreed reusable categories."""
    assets = root / "assets"
    if not assets.is_dir():
        # Surfaced by the top-level check; nothing more to do here.
        return []

    failures: list[Failure] = []
    for sub in _iter_immediate_subdirs(assets):
        name = sub.name
        if name in FORBIDDEN_ASSET_SUBDIRS:
            failures.append(
                Failure(
                    boundary="forbidden shared asset dir",
                    detail=(
                        f"{_rel(root, sub)} is a shared commands/prompts/"
                        f"tips asset directory; these are out of scope for "
                        f"reusable assets and must live under "
                        f"targets/<tool>/ instead"
                    ),
                )
            )
            continue
        if name not in ALLOWED_ASSET_CATEGORIES:
            failures.append(
                Failure(
                    boundary="asset category whitelist",
                    detail=(
                        f"{_rel(root, sub)} is not an agreed reusable "
                        f"asset category; allowed: "
                        f"{', '.join(sorted(ALLOWED_ASSET_CATEGORIES))}"
                    ),
                )
            )
    return failures


def check_target_templates(root: Path) -> list[Failure]:
    """Each runtime target exposes the right template and no live config."""
    failures: list[Failure] = []
    for target, spec in TARGET_TEMPLATES.items():
        target_dir = root / "targets" / target
        if not target_dir.is_dir():
            failures.append(
                Failure(
                    boundary="target landing area",
                    detail=(
                        f"missing target landing area: {_rel(root, target_dir)}; "
                        f"runtime target '{target}' must be a directory under targets/"
                    ),
                )
            )
            continue
        for template in spec["templates"]:
            template_path = target_dir / template
            if not template_path.is_file():
                failures.append(
                    Failure(
                        boundary="target template config",
                        detail=(
                            f"{_rel(root, template_path)} is missing; "
                            f"runtime target '{target}' must expose this "
                            f"template instead of a live config"
                        ),
                    )
                )
        for live in spec["forbidden_live"]:
            live_path = target_dir / live
            if live_path.exists():
                failures.append(
                    Failure(
                        boundary="live sensitive config",
                        detail=(
                            f"{_rel(root, live_path)} is committed; "
                            f"runtime target '{target}' must ship a "
                            f"`{live}.template` and keep the live file "
                            f"uncommitted"
                        ),
                    )
                )
    return failures


def check_shared_mcp_assets(root: Path) -> list[Failure]:
    """Shared MCP assets are cards, not runtime config snippets."""
    mcp_dir = root / "assets" / "mcp-servers"
    if not mcp_dir.is_dir():
        return []
    failures: list[Failure] = []
    for entry in sorted(mcp_dir.rglob("*")):
        if not entry.is_file() or entry.name.startswith("."):
            continue
        if entry.suffix.lower() in RUNTIME_CONFIG_EXTENSIONS:
            failures.append(
                Failure(
                    boundary="shared MCP asset shape",
                    detail=(
                        f"{_rel(root, entry)} is a runtime-native config "
                        f"snippet; shared MCP assets are server cards and "
                        f"must not contain {entry.suffix} wiring"
                    ),
                )
            )
    return failures


def check_shared_hook_assets(root: Path) -> list[Failure]:
    """Shared hook assets are policy notes, not executable implementations."""
    hooks_dir = root / "assets" / "hooks"
    if not hooks_dir.is_dir():
        return []
    failures: list[Failure] = []
    for entry in sorted(hooks_dir.rglob("*")):
        if not entry.is_file() or entry.name.startswith("."):
            continue
        suffix = entry.suffix.lower()
        if suffix == ".md":
            continue
        # Anything non-markdown is treated as a policy violation: shared
        # hooks are notes, not code. `.gitkeep` and other dotfiles are
        # filtered by the leading-dot check above.
        failures.append(
            Failure(
                boundary="shared hook asset shape",
                detail=(
                    f"{_rel(root, entry)} is not a policy note; shared "
                    f"hook assets are lifecycle policy descriptions and "
                    f"must be `.md` files (found {suffix or 'no extension'})"
                ),
            )
        )
    return failures


# --- Driver -------------------------------------------------------------------


CHECKS = (
    ("top-level areas", check_top_level),
    ("asset categories", check_asset_categories),
    ("target templates", check_target_templates),
    ("shared MCP assets", check_shared_mcp_assets),
    ("shared hook assets", check_shared_hook_assets),
)


def run(root: Path) -> list[Failure]:
    """Run every boundary check and return the collected failures."""
    failures: list[Failure] = []
    for _name, check in CHECKS:
        failures.extend(check(root))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the agent-configs repository structure and safety "
            "boundaries."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Path to the repository root (default: parent of this script).",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        print(f"validate_repo_structure: not a directory: {root}", file=sys.stderr)
        return 2

    failures = run(root)
    if not failures:
        print("validate_repo_structure: OK")
        print(
            "  checked: top-level areas, asset categories, target "
            "templates, shared MCP assets, shared hook assets"
        )
        return 0

    print("validate_repo_structure: FAILED", file=sys.stderr)
    for failure in failures:
        print(
            f"  [{failure.boundary}] {failure.detail}",
            file=sys.stderr,
        )
    print(
        f"  {len(failures)} architectural-boundary violation(s)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
