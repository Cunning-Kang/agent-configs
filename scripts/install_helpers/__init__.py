"""Lightweight install helpers for agent-configs.

This package provides a small, shared engine plus a thin per-tool wrapper
module. Each per-tool script (`install_claude_code.py`, `install_codex.py`,
`install_omp.py`) is a CLI front-end on top of :mod:`install_helpers.engine`.

The helpers are deliberately narrow: they perform mechanical copy or link
operations from this repo's `targets/<tool>/` landing area into a
user-supplied destination directory. They do not behave as a profile
manager, a rollback system, a remote sync tool, or a sensitive config
merger. See ``scripts/README.md`` for the full list of what they refuse to
do.
"""

from .engine import (
    Action,
    ActionKind,
    InstallEngine,
    InstallerResult,
    InstallPlan,
    DEFAULT_BACKUP_SUFFIX,
    SKIP_PATH_TOKENS,
    SKIP_FILENAMES,
)

__all__ = [
    "Action",
    "ActionKind",
    "InstallEngine",
    "InstallerResult",
    "InstallPlan",
    "DEFAULT_BACKUP_SUFFIX",
    "SKIP_PATH_TOKENS",
    "SKIP_FILENAMES",
]
