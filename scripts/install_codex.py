#!/usr/bin/env python3
"""Install helper for the Codex target.

Stages the contents of ``targets/codex/`` (agents, commands, hooks,
skills, and the config template) into a destination directory
(default ``~/.codex/``).

This is a thin wrapper around :mod:`install_helpers.engine`. It does
not merge live config, does not inject model routing or provider
credentials, and does not touch permission policy. The live config
file (``config.toml``) is *refused* by default and only staged
alongside an existing live file when ``--include-live-config`` is
passed.

Usage:

    # Safe default: report the plan, do not touch the destination.
    python3 scripts/install_codex.py

    # Apply the plan, copying files into ~/.codex/.
    python3 scripts/install_codex.py --apply

    # Symlink each file instead of copying.
    python3 scripts/install_codex.py --apply --link

    # Stage the template next to an existing live config without
    # touching the live file itself.
    python3 scripts/install_codex.py --apply --include-live-config

    # Show the protected live config filename.
    python3 scripts/install_codex.py --list-live-config
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from install_helpers.engine import build_parser, run_cli  # noqa: E402

TOOL_NAME = "codex"
SOURCE_SUBDIR = "targets/codex"
DEFAULT_DEST = "~/.codex"
LIVE_CONFIG = ("config.toml",)
DESCRIPTION = (
    "Install the Codex target into a destination directory. "
    "Copies (or symlinks) agents/, commands/, hooks/, skills/, and "
    "the config.toml.template. Refuses to overwrite live config.toml."
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
