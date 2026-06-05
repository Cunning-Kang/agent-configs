#!/usr/bin/env python3
"""Install helper for the Claude Code target.

Stages the contents of ``targets/claude-code/`` (skills, agents,
commands, hooks, and the settings/MCP template files) into a
destination directory (default ``~/.claude/``).

This is a thin wrapper around :mod:`install_helpers.engine`. It does
not merge live settings, does not inject secrets, and does not touch
permission policy. The live config files (``settings.json``,
``mcp.json``) are *refused* by default and only staged alongside an
existing live file when ``--include-live-config`` is passed.

Usage:

    # Safe default: report the plan, do not touch the destination.
    python3 scripts/install_claude_code.py

    # Apply the plan, copying files into ~/.claude/.
    python3 scripts/install_claude_code.py --apply

    # Symlink each file instead of copying (one-way mirror of the repo).
    python3 scripts/install_claude_code.py --apply --link

    # Stage the templates next to existing live config files without
    # touching the live files themselves.
    python3 scripts/install_claude_code.py --apply --include-live-config

    # Show the protected live config filenames.
    python3 scripts/install_claude_code.py --list-live-config
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the package importable regardless of invocation cwd.
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from install_helpers.engine import build_parser, run_cli  # noqa: E402

TOOL_NAME = "claude-code"
SOURCE_SUBDIR = "targets/claude-code"
DEFAULT_DEST = "~/.claude"
# Live config files that are never overwritten. The templates with the
# same stem are staged instead when --include-live-config is passed.
LIVE_CONFIG = (
    "settings.json",
    "mcp.json",
)
DESCRIPTION = (
    "Install the Claude Code target into a destination directory. "
    "Copies (or symlinks) agents/, commands/, skills/, hooks/, and "
    "the template config files. Refuses to overwrite live config."
)


def main(argv=None) -> int:
    parser = build_parser(
        tool_name=TOOL_NAME,
        default_dest=DEFAULT_DEST,
        live_config_files=LIVE_CONFIG,
        source_subdir=SOURCE_SUBDIR,
        description=DESCRIPTION,
    )
    return run_cli(parser, argv)


if __name__ == "__main__":
    raise SystemExit(main())
