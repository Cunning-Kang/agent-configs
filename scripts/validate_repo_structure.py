#!/usr/bin/env python3
"""Repository structure validator for the agent-configs landing repo.

Read-only decision record. Confirms the boundaries recorded in
`CONTEXT.md` and `assets/README.md` are intact, and that no
`*.template`-shadowed live config has been committed. Exits
non-zero on any violation.

The check is intentionally narrow: the validator does not look at
runtime *content* (e.g. agent bodies, hook bodies) — those are the
runtime runnability audit's job. It only enforces the structural
boundaries that, if violated, would let a default install distribute
something the user has not opted into or has no safe way to use.

Run with:

    python3 scripts/validate_repo_structure.py
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REQUIRED_TOP_LEVEL_AREAS: tuple[str, ...] = (
    "assets",
    "targets",
    "scripts",
    "inbox",
    "archive",
    "docs",
)
REQUIRED_MAINTENANCE_AREAS: tuple[str, ...] = ("docs/maintenance",)
ALLOWED_ASSET_CATEGORIES: frozenset[str] = frozenset(
    {"mcp-servers", "packs", "rules", "hooks", "agents", "skills"}
)
# `commands/`, `prompts/`, and `tips/` are explicitly NOT reusable
# assets: a command, prompt, or tip is owned by a single runtime
# tool and belongs under `targets/<tool>/`, not in `assets/`.
FORBIDDEN_ASSET_SUBDIRS: frozenset[str] = frozenset({"prompts", "commands", "tips"})

# Runtime-native config extensions that must not appear under the
# shared asset layers.
RUNTIME_CONFIG_EXTENSIONS: frozenset[str] = frozenset(
    {".toml", ".yml", ".json", ".yaml"}
)

# Per-target template + forbidden-live pairs. The template file is
# the only file that belongs in the repo; the live filename is
# machine-specific and must not be committed.
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


# Patterns that indicate a Claude Code slash command hard-codes an
# external dependency under the user's home directory. The accepted
# escape hatch is to resolve the same path through a documented
# environment variable, e.g. ``$FOO_BAR`` or ``${FOO_BAR}``. The check
# only looks at the markdown body outside YAML frontmatter, so a
# ``description:`` block that mentions the path for documentation
# purposes is not flagged.
_HARD_CODED_SCRIPT_PATH = re.compile(r"~/\.claude/scripts/[^\s`)\]\"'<>]+")
_HARD_CODED_BASELINE_PATH = re.compile(r"~/\.claude/baselines/[^\s`)\]\"'<>]+")
# Environment-variable references that, when present on the same line
# as a hard-coded path, document the override escape hatch the
# install-safety rule accepts. The check is intentionally lenient:
# any ``$NAME`` or ``${NAME}`` token on the line suppresses the
# failure for that line, mirroring how the rest of this repo
# documents env-var fallbacks.
_ENV_VAR_REFERENCE = re.compile(r"\$\{?[A-Z_][A-Z0-9_]*\}?")


def _split_frontmatter(text: str) -> str:
    """Return the markdown body with YAML frontmatter stripped.

    Slash-command frontmatter is the ``---``-delimited block at the
    top of the file. The check only enforces install safety against
    the body, so a ``description:`` block that references the path
    for documentation purposes is not flagged.
    """
    if not text.startswith("---"):
        return text
    lines = text.splitlines(keepends=True)
    for i in range(1, len(lines)):
        if lines[i].rstrip("\n") == "---":
            return "".join(lines[i + 1 :])
    # No closing frontmatter delimiter; treat the whole file as body.
    return text


def _line_has_env_var_override(line: str) -> bool:
    return _ENV_VAR_REFERENCE.search(line) is not None


def check_claude_code_command_install_safety(root: Path) -> list[Failure]:
    """Claude Code slash commands must not hard-code external paths.

    A command that the default target distributes must either be
    self-contained or document a local-placeholder / env-var escape
    hatch for every external dependency it invokes. The known-bad
    shape is an unconditional ``~/.claude/scripts/...`` or
    ``~/.claude/baselines/...`` reference in the command body.
    The archived ``new-feature`` command (see issue #14) is the
    canonical example: it called
    ``~/.claude/scripts/instantiate-feature.sh`` with no env-var
    fallback and read the baseline cache from
    ``~/.claude/baselines/durable-workflow-v1/`` (the env-var
    override for the baseline was documented but the script itself
    was not). The check rejects any command that re-introduces
    either hard-coded path without a per-line env-var override.
    """
    commands_dir = root / "targets" / "claude-code" / "commands"
    if not commands_dir.is_dir():
        # Surfaced by other checks; nothing to inspect here.
        return []
    failures: list[Failure] = []
    for entry in sorted(commands_dir.iterdir()):
        if not entry.is_file() or entry.name.startswith(".") or entry.suffix != ".md":
            continue
        try:
            text = entry.read_text(encoding="utf-8")
        except OSError:
            # The validator must not crash on a file the user can't
            # read; other boundaries will surface the missing file.
            continue
        body = _split_frontmatter(text)
        for lineno, line in enumerate(body.splitlines(), start=1):
            has_script = _HARD_CODED_SCRIPT_PATH.search(line) is not None
            has_baseline = _HARD_CODED_BASELINE_PATH.search(line) is not None
            if not (has_script or has_baseline):
                continue
            if _line_has_env_var_override(line):
                # Documented env-var fallback on the same line: the
                # command is install-safe.
                continue
            kind = "script" if has_script else "baseline"
            failures.append(
                Failure(
                    boundary="claude code command install safety",
                    detail=(
                        f"{_rel(root, entry)}:{lineno} hard-codes a "
                        f"home-relative {kind} path; the default Claude "
                        f"Code target must not distribute a command "
                        f"that calls a missing {kind} under "
                        f"~/.claude/. Either move the command to "
                        f"`archive/` (external-only) or document an "
                        f"env-var fallback for the {kind} on the same "
                        f"line (e.g. ``$FOO_PATH`` or "
                        f"``${{FOO_PATH}}``)."
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
    ("claude-code command install safety", check_claude_code_command_install_safety),
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
            "templates, shared MCP assets, shared hook assets, "
            "claude-code command install safety"
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
