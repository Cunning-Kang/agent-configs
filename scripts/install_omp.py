#!/usr/bin/env python3
"""Install helper for the oh-my-pi target.

Stages the contents of ``targets/oh-my-pi/`` (extensions, skills,
and the harness config template) into a destination directory
(default ``~/.omp/``).

This is a thin wrapper around :mod:`install_helpers.engine`. It does
not merge live config, does not inject runtime registration, and
does not touch orchestration policy. The live config file
(``omp.config.json``) is *refused* by default and only staged
alongside an existing live file when ``--include-live-config`` is
passed.

Usage:

    # Safe default: report the plan, do not touch the destination.
    python3 scripts/install_omp.py

    # Apply the plan, copying files into ~/.omp/.
    python3 scripts/install_omp.py --apply

    # Symlink each file instead of copying.
    python3 scripts/install_omp.py --apply --link

    # Stage the template next to an existing live config without
    # touching the live file itself.
    python3 scripts/install_omp.py --apply --include-live-config

    # Show the protected live config filename.
    python3 scripts/install_omp.py --list-live-config
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from install_helpers.engine import build_parser, run_cli  # noqa: E402

TOOL_NAME = "omp"
SOURCE_SUBDIR = "targets/oh-my-pi"
DEFAULT_DEST = "~/.omp"
LIVE_CONFIG = ("omp.config.json",)
DESCRIPTION = (
    "Install the oh-my-pi harness target into a destination "
    "directory. Copies (or symlinks) extensions/, skills/, and "
    "omp.config.json.template. Refuses to overwrite live "
    "omp.config.json."
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
