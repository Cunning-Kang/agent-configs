"""Mechanical engine for the oh-my-pi redacted live-config exporter.

The engine is responsible for four things:

1. Reading the local OMP live config (``config.yml`` and
   ``models.yml``) with a small, stdlib-only YAML loader. The loader
   is intentionally narrow: it only accepts the block-style subset
   the OMP runtime emits, and it raises a clear error otherwise.
2. Redacting fields that must not appear in the committed template
   (provider credentials, base URLs, model identifiers, local
   paths, machine-specific theme/thinking values).
3. Projecting the redacted config into the shape of the existing
   ``omp.config.json.template``, preserving harness-level fields
   (extensions, runtimes, inheritance, orchestration, env) so the
   committed template stays useful as a machine-specific starting
   point.
4. Producing a plan and a redaction summary the CLI can render for
   human review. The plan is the contract; applying the plan writes
   the produced template to the destination only when the caller
   passes ``--apply``.

Design constraints (kept narrow on purpose):

* Read-only on the live config. The engine opens ``config.yml`` and
  ``models.yml`` and never anything else in ``~/.omp/agent/``.
* No third-party dependencies. The stdlib is enough.
* Boring and predictable. The redaction rules are a closed
  whitelist; anything not on the list is either preserved
  (machine-neutral scalars) or refused.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence


# --- Defaults -----------------------------------------------------------------

#: Default location of the local OMP ``config.yml`` on a real machine.
#: Tests override this; the CLI default keeps the documented workflow
#: single-step (``python3 scripts/export_omp_config.py``).
DEFAULT_OMP_CONFIG_PATH: str = "~/.omp/agent/config.yml"

#: Default location of the local OMP ``models.yml`` on a real machine.
DEFAULT_MODELS_PATH: str = "~/.omp/agent/models.yml"

#: Default destination of the produced template inside this repo.
#: The exporter writes the produced template here when ``--apply`` is
#: passed. The path is the same as the committed template so a
#: successful run refreshes the committed artifact.
DEFAULT_OUTPUT_PATH: str = "targets/oh-my-pi/omp.config.json.template"

#: Path segments that name live runtime state. The exporter never
#: reads any input path whose segments include one of these tokens.
#: The list mirrors the install-helper SKIP_PATH_TOKENS so the two
#: tools share the same mental model of "live state".
RUNTIME_STATE_TOKENS: frozenset[str] = frozenset(
    {
        "secrets",
        "secret",
        "sessions",
        "session",
        "terminal-sessions",
        "cache",
        "logs",
        "log",
        "databases",
        "database",
        "db",
        "history",
        "histories",
        "keyring",
        "credentials",
        "credential",
        "tokens",
        "token",
        "storage",
        "cookies",
        "state",
        "runtime",
        "audit",
        "natives",
        "native",
        "install-id",
        "install_id",
    }
)

#: Basenames the exporter never opens even when supplied as a direct
#: argument. Refusing them up front protects the contract that the
#: exporter never reads live runtime state, even by accident.
RUNTIME_STATE_BASENAMES: frozenset[str] = frozenset(
    {
        "agent.db",
        "agent.db-shm",
        "agent.db-wal",
        "history.db",
        "history.db-shm",
        "history.db-wal",
        "models.db",
        "models.db-shm",
        "models.db-wal",
        "autoqa.db",
        "autoqa.db-shm",
        "autoqa.db-wal",
        "codebase-memory-mcp-omp-proxy.mjs",
    }
)

#: Default indentation used by the OMP runtime's YAML output. The
#: loader is keyed to 2-space indent; anything else is rejected
#: loudly so a future OMP change does not silently mis-parse.
YAML_INDENT_STEP: int = 2

#: Placeholders written into the produced template. Keeping them in
#: one place makes the redaction shape self-documenting and easy to
#: compare against the committed template.
PLACEHOLDER_API_KEY = "<api-key-or-env-reference>"
PLACEHOLDER_BASE_URL = "<provider-base-url>"
PLACEHOLDER_PROVIDER_ID = "<provider-id>"
PLACEHOLDER_PROVIDER_ID_PREFIX = "<provider-id-"
PLACEHOLDER_PROVIDER_ID_SUFFIX = ">"
PLACEHOLDER_MODEL_ID = "<model-id>"
PLACEHOLDER_MODEL_NAME = "<model-display-name>"
PLACEHOLDER_ABSOLUTE_PATH = "<absolute-path-on-this-machine>"
PLACEHOLDER_THEME_NAME = "<theme-name>"
PLACEHOLDER_THINKING_LEVEL = "<thinking-level>"
PLACEHOLDER_RUNTIME = "<runtime>"
PLACEHOLDER_REDACTED = "<redacted>"


#: Per-block schema whitelist. Each passthrough block in the live
#: ``config.yml`` is filtered down to the keys the committed
#: ``omp.config.json.template`` documents as machine-neutral
#: policy. Anything else is dropped and counted in
#: ``unknown_passthrough_dropped``. Nested whitelists (e.g.
#: ``task.isolation``) are expressed as ``{"isolation": (...)}``
#: entries whose tuple lists the allowed inner keys. Top-level
#: scalars that survive the whitelist are also deep-scanned for
#: secret-looking patterns by :func:`_scrub_passthrough_value`.
BLOCK_SCHEMAS: dict[str, tuple[str, ...] | dict[str, tuple[str, ...]]] = {
    "startup": ("quiet", "checkUpdate"),
    "retry": (
        "enabled",
        "maxRetries",
        "baseDelayMs",
        "fallbackRevertPolicy",
    ),
    "compaction": (
        "enabled",
        "reserveTokens",
        "keepRecentTokens",
        "autoContinue",
        "strategy",
    ),
    "skills": ("enabled",),
    "terminal": ("showImages",),
    "display": ("tabWidth", "showTokenUsage"),
    "task": {
        "isolation": ("mode",),
        "eager": (),
        "enableLsp": (),
    },
    "tools": ("discoveryMode",),
    "mcp": ("discoveryMode",),
    "secrets": ("enabled",),
    "marketplace": ("autoUpdate",),
    "dev": {"autoqa": ("consent",)},
}

#: Substrings that mark a scalar as secret-shaped. The redaction
#: matches case-insensitively. Any whitelisted scalar whose string
#: form contains one of these substrings is replaced with
#: :data:`PLACEHOLDER_REDACTED` rather than copied through.
_SECRET_SUBSTRINGS: tuple[str, ...] = (
    "sk-",
    "https?://",
    "/users/",
    "~/.omp",
    "postgres",
    "mysql",
    "://",
    "agent.db",
    "session",
    "cache",
    "history",
)


def _looks_like_secret(value: Any) -> bool:
    """Return ``True`` if ``value`` is a scalar that smells like a secret.

    Only strings are checked. Booleans, integers, ``None``, lists,
    and dicts are not secret-shaped on their own; their string
    form is never the literal that lands in the produced template.
    """

    if not isinstance(value, str):
        return False
    lowered = value.lower()
    for needle in _SECRET_SUBSTRINGS:
        if needle in lowered:
            return True
    return False


def _scrub_passthrough_value(
    value: Any, summary: RedactionSummary
) -> Any:
    """Apply the deep-scan to a scalar that already passed the whitelist."""

    if _looks_like_secret(value):
        summary.add("unknown_passthrough_dropped")
        return PLACEHOLDER_REDACTED
    return value


def _scrub_passthrough_block(
    block_name: str,
    block: Any,
    summary: RedactionSummary,
) -> Any:
    """Filter ``block`` to the schema listed under ``block_name``.

    Unknown keys are dropped and counted in
    ``unknown_passthrough_dropped``. Scalars that survive the
    whitelist are deep-scanned for secret-shaped patterns. The
    function is a no-op when ``block_name`` is not in
    :data:`BLOCK_SCHEMAS` (returns ``None`` so the caller knows to
    omit the key).
    """

    schema = BLOCK_SCHEMAS.get(block_name)
    if schema is None or not isinstance(block, Mapping):
        # No whitelist for this block, or input is not a mapping:
        # drop it entirely. The caller will not emit the key.
        if block is not None:
            summary.add("unknown_passthrough_dropped")
        return None
    allowed = schema
    out: dict = {}
    for key, value in block.items():
        if isinstance(allowed, Mapping):
            if key not in allowed:
                summary.add("unknown_passthrough_dropped")
                continue
            inner_allowed = allowed[key]
            if isinstance(value, Mapping):
                inner: dict = {}
                for inner_key, inner_value in value.items():
                    if not isinstance(inner_allowed, tuple) or inner_key not in inner_allowed:
                        summary.add("unknown_passthrough_dropped")
                        continue
                    scrubbed = _scrub_passthrough_value(
                        inner_value, summary
                    )
                    if scrubbed is not None:
                        inner[inner_key] = scrubbed
                if inner:
                    out[key] = inner
            elif isinstance(inner_allowed, tuple) and inner_allowed == ():
                # A whitelisted scalar key: pass through after
                # the secret-pattern deep scan.
                scrubbed = _scrub_passthrough_value(value, summary)
                if scrubbed is not None:
                    out[key] = scrubbed
            else:
                # Mismatched shape (e.g. scalar where a mapping
                # is expected). Drop it.
                summary.add("unknown_passthrough_dropped")
        else:
            if key not in allowed:
                summary.add("unknown_passthrough_dropped")
                continue
            scrubbed = _scrub_passthrough_value(value, summary)
            if scrubbed is not None:
                out[key] = scrubbed
    return out


# --- YAML loader --------------------------------------------------------------


class YAMLError(ValueError):
    """Raised when a YAML input is outside the supported subset.

    The loader is intentionally narrow: it accepts the block-style
    mappings and sequences the OMP runtime emits and nothing else.
    Anything else is a hard error, not a silent best-effort parse.
    """


# Scalar coercion rules. We follow the OMP runtime's actual emission
# style: booleans are ``true``/``false`` (lowercase), null is never
# used, integers are decimal. Anything else is kept as a string and
# stripped of surrounding whitespace.
_BOOL_TRUE = frozenset({"true", "True", "TRUE", "yes", "Yes", "YES"})
_BOOL_FALSE = frozenset({"false", "False", "FALSE", "no", "No", "NO"})


def _coerce_scalar(text: str) -> Any:
    """Coerce a YAML scalar to a Python value."""
    if text == "" or text is None:
        return None
    stripped = text.strip()
    if stripped in _BOOL_TRUE:
        return True
    if stripped in _BOOL_FALSE:
        return False
    if re.fullmatch(r"-?\d+", stripped):
        return int(stripped)
    return stripped


def _indent_of(line: str) -> int:
    """Return the leading-space count of ``line``."""
    if "\t" in line:
        raise YAMLError(
            f"tab character in YAML line is not supported: {line!r}"
        )
    return len(line) - len(line.lstrip(" "))


def _is_blank_or_comment(line: str) -> bool:
    stripped = line.strip()
    return stripped == "" or stripped.startswith("#")


def _parse_mapping(
    lines: Sequence[str], start: int, indent: int, first_body: str
) -> tuple[dict, int]:
    """Parse a block mapping at ``indent`` columns.

    ``first_body`` is the text after the indent of the first key on
    ``lines[start]``; the caller has already verified it contains a
    colon.
    """

    out: dict = {}
    i = start
    while i < len(lines):
        line = lines[i]
        if _is_blank_or_comment(line):
            i += 1
            continue
        if _indent_of(line) < indent:
            break
        if _indent_of(line) > indent:
            raise YAMLError(
                f"line {i + 1}: unexpected over-indent in mapping: {line!r}"
            )
        body = line[indent:]
        if body.startswith("- "):
            break
        key, sep, value = body.partition(":")
        if not sep:
            raise YAMLError(
                f"line {i + 1}: mapping entry missing ':' in {line!r}"
            )
        key = key.strip()
        value = value.lstrip()
        if value == "":
            child_indent = indent + YAML_INDENT_STEP
            if i + 1 >= len(lines):
                out[key] = None
                i += 1
                break
            next_line = lines[i + 1]
            if _is_blank_or_comment(next_line) or _indent_of(next_line) <= indent:
                out[key] = None
                i += 1
                continue
            child, i = _split_block(lines, i + 1, child_indent)
            out[key] = child
        else:
            out[key] = _coerce_scalar(value)
            i += 1
    return out, i


def _parse_sequence(
    lines: Sequence[str], start: int, indent: int, first_body: str
) -> tuple[list, int]:
    """Parse a block sequence at ``indent`` columns.

    The OMP runtime emits two sequence shapes:

    * ``- scalar`` lists (``extensions: - ~/.omp/agent/...``)
    * inline-mapping items (``models: - id: Opus / name: Opus``)
      whose continuation lines land one indent step deeper than
      the sequence's own ``-`` column.

    The continuation case is tracked via a separate ``pending``
    dict that is *not* aliased into ``items`` until the mapping
    closes. This keeps a partly-built inline mapping out of the
    final list until all of its continuation keys have arrived.
    """

    items: list = []
    i = start
    pending: Optional[dict] = None
    merge_indent: Optional[int] = None

    def close_pending() -> None:
        nonlocal pending, merge_indent
        if pending is not None:
            items.append(pending)
        pending = None
        merge_indent = None

    while i < len(lines):
        line = lines[i]
        if _is_blank_or_comment(line):
            i += 1
            continue
        line_indent = _indent_of(line)
        if line_indent < indent:
            close_pending()
            break
        # Continuation of a pending inline mapping. Check this
        # *before* the dash-prefix checks: a continuation key
        # lands at a deeper indent than the sequence's own dash
        # column, so its body slice (at the sequence indent) does
        # not start with ``-`` even though it is part of the
        # sequence.
        if (
            pending is not None
            and merge_indent is not None
            and line_indent == merge_indent
        ):
            rest = line[merge_indent:]
            key, sep, value = rest.partition(":")
            if not sep:
                # Not a key/value pair. Close the pending
                # mapping and re-process this line at the
                # current level.
                close_pending()
                continue
            key = key.strip()
            value = value.lstrip()
            if value == "":
                child_indent = merge_indent + YAML_INDENT_STEP
                if i + 1 >= len(lines):
                    pending[key] = None
                    i += 1
                    continue
                next_line = lines[i + 1]
                if (
                    _is_blank_or_comment(next_line)
                    or _indent_of(next_line) <= merge_indent
                ):
                    pending[key] = None
                    i += 1
                    continue
                child, i = _split_block(lines, i + 1, child_indent)
                pending[key] = child
            else:
                pending[key] = _coerce_scalar(value)
                i += 1
            continue
        body = line[indent:]
        if body.startswith("- "):
            close_pending()
            item_text = body[2:]
            if ":" in item_text and not item_text.startswith("#"):
                key, _, value = item_text.partition(":")
                key = key.strip()
                value = value.strip()
                if value == "":
                    child_indent = indent + YAML_INDENT_STEP
                    if i + 1 >= len(lines):
                        items.append({key: None})
                        i += 1
                        continue
                    next_line = lines[i + 1]
                    if (
                        _is_blank_or_comment(next_line)
                        or _indent_of(next_line) <= indent
                    ):
                        items.append({key: None})
                        i += 1
                        continue
                    child, i = _split_block(lines, i + 1, child_indent)
                    items.append({key: child})
                else:
                    # Hold the new inline mapping in a separate
                    # ``pending`` dict instead of appending it to
                    # ``items`` immediately. The mapping is only
                    # committed to ``items`` once its continuation
                    # keys have all arrived (``close_pending``),
                    # so a half-built mapping is never observable
                    # by the caller.
                    pending = {key: _coerce_scalar(value)}
                    i += 1
                    merge_indent = indent + YAML_INDENT_STEP
            elif item_text == "":
                child_indent = indent + YAML_INDENT_STEP
                child, i = _split_block(lines, i + 1, child_indent)
                items.append(child)
            else:
                items.append(_coerce_scalar(item_text))
                i += 1
            continue
        if not body.startswith("-"):
            close_pending()
            break
        raise YAMLError(
            f"line {i + 1}: unexpected line in sequence at indent "
            f"{indent}: {line!r}"
        )
    close_pending()
    return items, i


def _split_block(
    lines: Sequence[str], start: int, indent: int
) -> tuple[Any, int]:
    """Parse one block at ``indent`` columns starting at ``lines[start]``."""

    if start >= len(lines):
        return None, start

    line = lines[start]
    if _indent_of(line) != indent:
        raise YAMLError(
            f"line {start + 1}: expected indent {indent}, got "
            f"{_indent_of(line)}: {line!r}"
        )

    body = line[indent:]
    if body.startswith("- "):
        return _parse_sequence(lines, start, indent, body[2:])
    if body == "-":
        return _parse_sequence(lines, start, indent, "")
    if ":" in body:
        return _parse_mapping(lines, start, indent, body)
    return _coerce_scalar(body), start + 1


def load_yaml(text: str) -> Any:
    """Parse a YAML document using the supported block-style subset.

    Raises :class:`YAMLError` for any input outside the subset the
    OMP runtime emits.
    """

    text = text.lstrip("\ufeff")
    raw_lines = text.splitlines()
    lines: list[str] = [
        raw for raw in raw_lines if not _is_blank_or_comment(raw)
    ]
    if not lines:
        return {}

    first = lines[0]
    if _indent_of(first) != 0:
        raise YAMLError(
            f"line 1: top-level YAML must start at column 0, got "
            f"indent {_indent_of(first)}: {first!r}"
        )

    body = first.lstrip(" ")
    if body.startswith("- "):
        parsed, _ = _parse_sequence(lines, 0, 0, body[2:])
        return parsed
    if ":" in body:
        parsed, _ = _parse_mapping(lines, 0, 0, body)
        return parsed
    return _coerce_scalar(body)


# --- Redaction summary --------------------------------------------------------


@dataclass
class RedactionSummary:
    """A count of redactions applied during a single export."""

    api_keys: int = 0
    base_urls: int = 0
    provider_ids: int = 0
    model_ids: int = 0
    model_names: int = 0
    absolute_paths: int = 0
    thinking_levels: int = 0
    theme_names: int = 0
    runtimes: int = 0
    providers_dropped: int = 0
    provider_blocks_redacted: int = 0
    unknown_passthrough_dropped: int = 0

    def add(self, category: str, count: int = 1) -> None:
        """Add ``count`` to the named category.

        Unknown categories raise so a typo in a redaction rule is
        caught at test time rather than after a commit.
        """
        if not hasattr(self, category):
            raise ValueError(f"unknown redaction category: {category}")
        setattr(self, category, getattr(self, category) + count)

    def as_dict(self) -> dict[str, int]:
        return {
            "api_keys": self.api_keys,
            "base_urls": self.base_urls,
            "provider_ids": self.provider_ids,
            "model_ids": self.model_ids,
            "model_names": self.model_names,
            "absolute_paths": self.absolute_paths,
            "thinking_levels": self.thinking_levels,
            "theme_names": self.theme_names,
            "runtimes": self.runtimes,
            "providers_dropped": self.providers_dropped,
            "provider_blocks_redacted": self.provider_blocks_redacted,
            "unknown_passthrough_dropped": self.unknown_passthrough_dropped,
        }

    def total(self) -> int:
        return sum(self.as_dict().values())


# --- Plan / result types ------------------------------------------------------


@dataclass
class ExportPlan:
    """The exporter's plan: what it will read, redact, and write."""

    config_path: Path
    models_path: Path
    output_path: Path
    config_loaded: bool = False
    models_loaded: bool = False
    redactions: RedactionSummary = field(default_factory=RedactionSummary)
    refused_inputs: list[tuple[Path, str]] = field(default_factory=list)
    produced_template: Optional[dict] = None
    produced_text: Optional[str] = None

    def is_empty(self) -> bool:
        return self.produced_template is None


@dataclass
class ExporterResult:
    """The outcome of an applied export."""

    plan: ExportPlan
    written: bool = False

    def summary_line(self) -> str:
        return (
            f"wrote={self.written} "
            f"redactions={self.plan.redactions.total()} "
            f"refused_inputs={len(self.plan.refused_inputs)}"
        )


# --- Loader wrappers ----------------------------------------------------------


def _validate_input_path(
    path: Path, role: str
) -> list[tuple[Path, str]]:
    """Refuse input paths that look like live runtime state."""

    refusals: list[tuple[Path, str]] = []
    name_lower = path.name.lower()
    if name_lower in RUNTIME_STATE_BASENAMES:
        refusals.append(
            (
                path,
                f"{path.name} is a live runtime state file; refusing to read",
            )
        )
        return refusals
    for part in path.parts:
        part_lower = part.lower()
        if part_lower in RUNTIME_STATE_TOKENS:
            refusals.append(
                (
                    path,
                    f"path segment {part!r} names live runtime state; refusing to read",
                )
            )
            break
    return refusals


def load_omp_config_yml(path: Path) -> dict:
    """Load the OMP ``config.yml`` and return it as a dict."""

    if not path.exists():
        raise FileNotFoundError(f"OMP config.yml not found: {path}")
    refusals = _validate_input_path(path, "config")
    if refusals:
        raise PermissionError(refusals[0][1])
    text = path.read_text(encoding="utf-8")
    parsed = load_yaml(text)
    if not isinstance(parsed, dict):
        raise YAMLError(
            f"OMP config.yml must be a mapping at the top level, "
            f"got {type(parsed).__name__}"
        )
    return parsed


def load_models_yml(path: Path) -> dict:
    """Load the OMP ``models.yml`` and return it as a dict."""

    if not path.exists():
        raise FileNotFoundError(f"OMP models.yml not found: {path}")
    refusals = _validate_input_path(path, "models")
    if refusals:
        raise PermissionError(refusals[0][1])
    text = path.read_text(encoding="utf-8")
    parsed = load_yaml(text)
    if not isinstance(parsed, dict):
        raise YAMLError(
            f"OMP models.yml must be a mapping at the top level, "
            f"got {type(parsed).__name__}"
        )
    return parsed


# --- Redaction logic ----------------------------------------------------------


def _redact_model_role_value(
    value: Any, summary: RedactionSummary
) -> Any:
    """Redact a ``modelRoles.*`` value."""

    if not isinstance(value, str):
        return value
    summary.add("model_ids")
    return PLACEHOLDER_MODEL_ID


def _redact_theme(value: Any, summary: RedactionSummary) -> Any:
    if isinstance(value, str) and value != "":
        summary.add("theme_names")
        return PLACEHOLDER_THEME_NAME
    return value


def _redact_thinking_level(
    value: Any, summary: RedactionSummary
) -> Any:
    if isinstance(value, str) and value != "":
        summary.add("thinking_levels")
        return PLACEHOLDER_THINKING_LEVEL
    return value


def _redact_extension_path(
    value: Any, summary: RedactionSummary
) -> Any:
    """Redact a single entry in the ``extensions`` sequence."""

    if not isinstance(value, str):
        return value
    if value == "":
        return value
    summary.add("absolute_paths")
    return PLACEHOLDER_ABSOLUTE_PATH


def _redact_single_provider(
    provider: Any, summary: RedactionSummary
) -> dict:
    """Redact the contents of a single provider entry."""

    if not isinstance(provider, dict):
        return {"_redacted": True}
    out: dict = {}
    base_url = provider.get("baseUrl")
    if isinstance(base_url, str) and base_url != "":
        summary.add("base_urls")
        out["baseUrl"] = PLACEHOLDER_BASE_URL
    api_key = provider.get("apiKey")
    if isinstance(api_key, str) and api_key != "":
        summary.add("api_keys")
        out["apiKey"] = PLACEHOLDER_API_KEY
    for passthrough in ("api", "auth"):
        if passthrough in provider:
            out[passthrough] = provider[passthrough]
    models = provider.get("models")
    if isinstance(models, list):
        out_models: list = []
        for entry in models:
            if not isinstance(entry, dict):
                continue
            redacted_entry: dict = {}
            if "id" in entry and entry["id"] != "":
                summary.add("model_ids")
                redacted_entry["id"] = PLACEHOLDER_MODEL_ID
            if "name" in entry and entry["name"] != "":
                summary.add("model_names")
                redacted_entry["name"] = PLACEHOLDER_MODEL_NAME
            for passthrough in (
                "api",
                "reasoning",
                "input",
                "contextWindow",
                "maxTokens",
            ):
                if passthrough in entry:
                    redacted_entry[passthrough] = entry[passthrough]
            out_models.append(redacted_entry)
        out["models"] = out_models
    return out


def _synthesize_provider_key(index: int) -> str:
    """Return the placeholder key for the ``index``-th provider.

    The first provider keeps the unsuffixed placeholder
    (``<provider-id>``) so the existing single-provider fixtures
    and committed template shape are unchanged. Subsequent
    providers are numbered (``<provider-id-2>``, ``<provider-id-3>``,
    ...). Counting starts at 1 for readability; index 0 is the
    first provider.
    """

    if index <= 0:
        return PLACEHOLDER_PROVIDER_ID
    return (
        f"{PLACEHOLDER_PROVIDER_ID_PREFIX}"
        f"{index + 1}{PLACEHOLDER_PROVIDER_ID_SUFFIX}"
    )


def _redact_providers_block(
    providers: Mapping[str, Any], summary: RedactionSummary
) -> dict:
    """Redact every provider entry and return a sanitized block.

    Each provider is keyed by a unique placeholder so multiple
    providers survive the export without clobbering each other.
    The first provider uses the bare ``<provider-id>`` key (so
    the single-provider shape the committed template documents is
    unchanged); the second and following providers get
    ``<provider-id-2>``, ``<provider-id-3>``, and so on.
    """

    out: dict = {}
    for index, (_provider_id, provider) in enumerate(providers.items()):
        summary.add("provider_ids")
        redacted = _redact_single_provider(provider, summary)
        out[_synthesize_provider_key(index)] = redacted
        summary.add("provider_blocks_redacted")
    return out


def redact_config(
    config: Mapping[str, Any], summary: Optional[RedactionSummary] = None
) -> dict:
    """Project a live ``config.yml`` mapping into the template shape.

    Top-level passthrough fields are filtered through
    :data:`BLOCK_SCHEMAS` (and the secret-pattern deep scan in
    :func:`_scrub_passthrough_block`) so unknown or secret-shaped
    sub-keys never reach the produced template. The
    ``unknown_passthrough_dropped`` counter on ``summary`` records
    how many keys were discarded.
    """

    summary = summary if summary is not None else RedactionSummary()
    out: dict = {}

    roles = config.get("modelRoles")
    if isinstance(roles, dict):
        out_roles: dict = {}
        for role_name, role_value in roles.items():
            out_roles[role_name] = _redact_model_role_value(
                role_value, summary
            )
        out["modelRoles"] = out_roles

    if "defaultThinkingLevel" in config:
        out["defaultThinkingLevel"] = _redact_thinking_level(
            config["defaultThinkingLevel"], summary
        )

    # Top-level scalar passthroughs documented in the committed
    # template. Each is checked as a single value, not a block.
    for scalar_passthrough in (
        "steeringMode",
        "interruptMode",
        "hideThinkingBlock",
        "symbolPreset",
    ):
        if scalar_passthrough in config:
            value = config[scalar_passthrough]
            scrubbed = _scrub_passthrough_value(value, summary)
            if scrubbed is not None:
                out[scalar_passthrough] = scrubbed

    # Block passthroughs go through the schema whitelist. The
    # whitelist for each block is the curated subset the
    # committed template documents as machine-neutral policy.
    for block_name in BLOCK_SCHEMAS:
        if block_name not in config:
            continue
        scrubbed = _scrub_passthrough_block(
            block_name, config[block_name], summary
        )
        if scrubbed:
            out[block_name] = scrubbed

    extensions = config.get("extensions")
    if isinstance(extensions, list):
        out["extensions"] = {
            "load_paths": [
                _redact_extension_path(item, summary) for item in extensions
            ]
        }

    theme = config.get("theme")
    if isinstance(theme, dict):
        out_theme: dict = {}
        if "dark" in theme:
            out_theme["dark"] = _redact_theme(theme["dark"], summary)
        if "light" in theme:
            out_theme["light"] = _redact_theme(theme["light"], summary)
        out["theme"] = out_theme

    return out


# --- Plan construction --------------------------------------------------------


def _build_template(
    config: Optional[Mapping[str, Any]],
    models: Optional[Mapping[str, Any]],
    summary: RedactionSummary,
) -> dict:
    """Combine the redacted config with the redacted providers block."""

    out: dict = {}
    if config is not None:
        out.update(redact_config(config, summary))

    if models is not None:
        providers = models.get("providers")
        if isinstance(providers, dict):
            out["providers"] = _redact_providers_block(providers, summary)
        else:
            summary.add("providers_dropped")

    out.setdefault("setupVersion", 1)
    if "runtimes" not in out:
        out["runtimes"] = {
            "claude-code": {"landing": "targets/claude-code"},
            "codex": {"landing": "targets/codex"},
        }
    if "inheritance" not in out:
        out["inheritance"] = {
            "load_assets_first": True,
            "compose_with_targets": True,
        }
    if "orchestration" not in out:
        default_chain = [PLACEHOLDER_RUNTIME, PLACEHOLDER_RUNTIME]
        for _ in default_chain:
            summary.add("runtimes")
        out["orchestration"] = {
            "default_chain": default_chain,
            "policies": [],
        }
    if "env" not in out:
        out["env"] = {
            "EXAMPLE_LOCAL_PATH": PLACEHOLDER_ABSOLUTE_PATH,
        }
    return out


def export_to_template(
    config_path: Path,
    models_path: Path,
    output_path: Path,
    *,
    allow_missing_config: bool = False,
    allow_missing_models: bool = True,
) -> ExportPlan:
    """Build an :class:`ExportPlan` from the given input paths."""

    plan = ExportPlan(
        config_path=config_path,
        models_path=models_path,
        output_path=output_path,
    )

    config: Optional[dict] = None
    models: Optional[dict] = None

    config_refusals = _validate_input_path(config_path, "config")
    if config_refusals:
        plan.refused_inputs.extend(config_refusals)
    else:
        try:
            config = load_omp_config_yml(config_path)
            plan.config_loaded = True
        except FileNotFoundError:
            if not allow_missing_config:
                plan.refused_inputs.append(
                    (
                        config_path,
                        "config.yml not found; pass --allow-missing-config "
                        "to produce a template from models.yml only",
                    )
                )
        except (YAMLError, PermissionError) as exc:
            plan.refused_inputs.append((config_path, str(exc)))

    models_refusals = _validate_input_path(models_path, "models")
    if models_refusals:
        plan.refused_inputs.extend(models_refusals)
    else:
        try:
            models = load_models_yml(models_path)
            plan.models_loaded = True
        except FileNotFoundError:
            if not allow_missing_models:
                plan.refused_inputs.append(
                    (
                        models_path,
                        "models.yml not found; pass --require-models to "
                        "fail loudly when the providers block is missing",
                    )
                )
        except (YAMLError, PermissionError) as exc:
            plan.refused_inputs.append((models_path, str(exc)))

    if not plan.config_loaded and not plan.models_loaded:
        return plan

    produced = _build_template(config, models, plan.redactions)
    plan.produced_template = produced
    plan.produced_text = json.dumps(produced, indent=2, sort_keys=False) + "\n"
    return plan


def _write_plan(plan: ExportPlan, *, force: bool = False) -> bool:
    """Write ``plan.produced_text`` to ``plan.output_path``.

    Refuses to overwrite an existing file unless ``force`` is set.
    """

    if plan.produced_text is None:
        return False
    out = plan.output_path
    if out.exists() and not force:
        raise FileExistsError(
            f"refusing to overwrite existing file: {out}; "
            f"re-run with --force to rotate the existing template"
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(plan.produced_text, encoding="utf-8")
    return True


# --- CLI rendering ------------------------------------------------------------


def render_plan(plan: ExportPlan, stream=sys.stdout) -> None:
    """Render the plan to ``stream`` in a stable, readable format."""

    print(
        f"[export-plan] {plan.config_path} + {plan.models_path} -> {plan.output_path}",
        file=stream,
    )
    if plan.config_loaded:
        print(f"  READ   {plan.config_path}", file=stream)
    if plan.models_loaded:
        print(f"  READ   {plan.models_path}", file=stream)
    for path, reason in plan.refused_inputs:
        print(f"  REFUSE {path}  ({reason})", file=stream)
    if plan.produced_template is not None:
        print(f"  WRITE  {plan.output_path}", file=stream)
        counts = plan.redactions.as_dict()
        rendered_counts = " ".join(
            f"{key}={value}" for key, value in counts.items() if value
        )
        if rendered_counts:
            print(f"  REDACT {rendered_counts}", file=stream)


# --- CLI driver ---------------------------------------------------------------


def build_exporter_parser() -> argparse.ArgumentParser:
    """Build the standard argparse parser for the exporter CLI."""

    default_config = Path(DEFAULT_OMP_CONFIG_PATH).expanduser()
    default_models = Path(DEFAULT_MODELS_PATH).expanduser()
    default_output = Path(DEFAULT_OUTPUT_PATH)

    parser = argparse.ArgumentParser(
        prog="export_omp_config",
        description=(
            "Export the local oh-my-pi live config into a sanitized "
            "omp.config.json.template. Read-only by default; pass "
            "--apply to write the produced template to disk."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=default_config,
        help=(
            "Path to the local OMP config.yml "
            f"(default: {default_config})"
        ),
    )
    parser.add_argument(
        "--models",
        type=Path,
        default=default_models,
        help=(
            "Path to the local OMP models.yml "
            f"(default: {default_models})"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output,
        help=(
            "Destination path for the produced template "
            f"(default: {default_output})"
        ),
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent,
        help=(
            "Path to the agent-configs repository root. Used to "
            "resolve the default --output path "
            "(default: parent of scripts/)."
        ),
    )
    parser.add_argument(
        "--apply",
        dest="apply",
        action="store_true",
        help=(
            "Write the produced template to --output. The default "
            "is dry-run: the plan is rendered and nothing is "
            "written."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Overwrite an existing --output file. The exporter "
            "refuses to clobber the committed template by "
            "default; --force is the explicit opt-in."
        ),
    )
    parser.add_argument(
        "--allow-missing-config",
        action="store_true",
        help=(
            "Produce a template even when --config is missing. "
            "Useful for a models-only export."
        ),
    )
    parser.add_argument(
        "--require-models",
        action="store_true",
        help=(
            "Fail the export when --models is missing. Default "
            "is to record a REFUSE on the plan and continue, so "
            "a config-only export still works."
        ),
    )
    return parser


def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    """Resolve the input and output paths against ``--repo``."""

    repo = args.repo.resolve()
    config_path = args.config.expanduser()
    models_path = args.models.expanduser()
    output_path = args.output
    if not output_path.is_absolute():
        output_path = repo / output_path
    return config_path, models_path, output_path


#: Exit code returned when ``--apply`` is requested but the plan
#: has at least one refused input. Distinct from 1 (no plan) and
#: 3 (refused overwrite) so callers can tell the failure mode
#: without parsing stderr.
EXIT_REFUSED_APPLY = 4


def run_cli(argv: Optional[Sequence[str]] = None) -> int:
    """Drive the exporter CLI end-to-end.

    Returns a Unix-style exit code: 0 on success, 1 on validation
    failure, 3 on a refused write, 4 on ``--apply`` with refused
    inputs.
    """

    parser = build_exporter_parser()
    args = parser.parse_args(argv)
    config_path, models_path, output_path = _resolve_paths(args)

    plan = export_to_template(
        config_path=config_path,
        models_path=models_path,
        output_path=output_path,
        allow_missing_config=args.allow_missing_config,
        allow_missing_models=not args.require_models,
    )

    if args.apply:
        print(f"[apply] omp_config_exporter: writing -> {output_path}")
    else:
        print(
            f"[dry-run] omp_config_exporter: planning -> {output_path}"
        )
    render_plan(plan)

    if plan.produced_template is None:
        print(
            "omp_config_exporter: nothing to export; check the "
            "--config and --models paths above",
            file=sys.stderr,
        )
        return 1

    if args.apply and plan.refused_inputs:
        # Refuse to write a template that was redacted from a
        # partial input. The user must either resolve the
        # refused input (e.g. point --config away from agent.db)
        # or drop --apply.
        print(
            "omp_config_exporter: --apply refused because the plan "
            "has refused inputs; re-run without --apply to inspect "
            "the plan, or fix the refused inputs first",
            file=sys.stderr,
        )
        for path, reason in plan.refused_inputs:
            print(f"omp_config_exporter:   REFUSE {path} ({reason})",
                  file=sys.stderr)
        return EXIT_REFUSED_APPLY

    if args.apply:
        try:
            wrote = _write_plan(plan, force=args.force)
        except FileExistsError as exc:
            print(f"omp_config_exporter: {exc}", file=sys.stderr)
            return 3
        result = ExporterResult(plan=plan, written=wrote)
        print(f"[apply] done. {result.summary_line()}")
    else:
        print(
            f"[dry-run] plan summary: redactions={plan.redactions.total()} "
            f"refused_inputs={len(plan.refused_inputs)}"
        )
    return 0
