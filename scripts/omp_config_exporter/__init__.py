"""Redacted live-config exporter for the oh-my-pi target.

This package turns the local oh-my-pi runtime configuration
(``config.yml`` and ``models.yml``) into a sanitized
``omp.config.json.template`` shape. It is a read-only counterpart to
:mod:`install_helpers.engine`: where the installer copies reusable
material from the repo into the machine, this exporter extracts the
shape of a single machine's live config and projects it back into a
committed template with credentials, base URLs, model identifiers, and
local paths replaced by placeholders.

The exporter is deliberately narrow:

* It only reads ``config.yml`` and ``models.yml``. It never touches
  sessions, terminal sessions, logs, caches, ``*.db*`` files,
  ``.mjs`` proxies, install IDs, histories, or audit logs.
* It always redacts known-sensitive fields and tracks the count for
  the summary line. A placeholder is the contract; a leaked literal
  is a regression.
* It is dry-run by default. Writing the produced template to disk
  requires an explicit ``--apply`` flag.
"""

from __future__ import annotations

from .engine import (
    DEFAULT_MODELS_PATH,
    DEFAULT_OMP_CONFIG_PATH,
    EXIT_REFUSED_APPLY,
    ExporterResult,
    ExportPlan,
    RedactionSummary,
    build_exporter_parser,
    export_to_template,
    load_models_yml,
    load_omp_config_yml,
    redact_config,
    render_plan,
    run_cli,
)

__all__ = [
    "DEFAULT_MODELS_PATH",
    "DEFAULT_OMP_CONFIG_PATH",
    "EXIT_REFUSED_APPLY",
    "ExportPlan",
    "ExporterResult",
    "RedactionSummary",
    "build_exporter_parser",
    "export_to_template",
    "load_models_yml",
    "load_omp_config_yml",
    "redact_config",
    "render_plan",
    "run_cli",
]
