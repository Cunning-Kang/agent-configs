#!/usr/bin/env python3
"""Command-line entry point for the oh-my-pi redacted config exporter.

This script is a thin wrapper around
:mod:`omp_config_exporter.engine`. It reads the local OMP
``config.yml`` and ``models.yml``, projects them into a sanitized
``omp.config.json.template`` shape, and either prints a plan (the
default) or writes the produced template to the destination path
(with ``--apply``).

The exporter is read-only on the live OMP config and never reads
sessions, terminal sessions, logs, caches, ``*.db*`` files,
``natives/``, install IDs, histories, or audit logs. Live secrets
and machine-specific values are redacted; the count of each kind of
redaction is reported for review.

Usage:

    # Dry-run: print the plan and redaction summary, write nothing.
    python3 scripts/export_omp_config.py

    # Apply: write the produced template to
    # targets/oh-my-pi/omp.config.json.template inside the repo.
    python3 scripts/export_omp_config.py --apply

    # Apply with an explicit overwrite of the existing template.
    python3 scripts/export_omp_config.py --apply --force

    # Use non-default input paths (handy for tests and CI).
    python3 scripts/export_omp_config.py \\
        --config /path/to/config.yml \\
        --models /path/to/models.yml \\
        --output /tmp/omp.config.json.template

    # Stage the produced template next to the existing one
    # without overwriting it.
    python3 scripts/export_omp_config.py \\
        --output targets/oh-my-pi/omp.config.json.template.next
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from omp_config_exporter.engine import run_cli  # noqa: E402


def main(argv=None) -> int:
    return run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
