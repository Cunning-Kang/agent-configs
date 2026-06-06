#!/usr/bin/env python3
"""Focused tests for the oh-my-pi redacted live-config exporter.

The test suite builds small, in-memory input trees that mirror the
shape of the live OMP ``config.yml`` and ``models.yml``, then
exercises the engine and the CLI end-to-end. Behaviour covered:

* YAML loader parses block-style mappings, sequences of scalars,
  and inline-mapping sequence items (the ``- id: Opus`` form the
  OMP runtime emits).
* Redaction replaces credentials, base URLs, model identifiers,
  theme names, thinking levels, extension paths, and per-provider
  blocks with placeholders. Multi-provider inputs are emitted
  with unique placeholder keys (``<provider-id>``, ``<provider-id-2>``,
  ...) so no provider silently clobbers another.
* Per-block schema whitelists drop unknown passthrough keys and
  bump an ``unknown_passthrough_dropped`` counter; a deep scan
  replaces any surviving scalar that looks like a secret with
  ``<redacted>``.
* Missing files produce a plan with a REFUSE rather than crashing.
* ``--apply`` together with a refused input exits non-zero
  (status 4) and leaves ``--output`` untouched.
* Runtime-state token paths (``agent.db``, ``sessions``,
  ``terminal-sessions``, ``cache``, ``logs``, etc.) are refused
  up front, even when passed as a direct argument.
* Dry-run is the default; ``--apply`` writes the produced
  template to ``--output``; ``--force`` overwrites an existing
  output.
* The redaction summary is rendered on the plan and is sufficient
  to verify that every live value has been redacted.

Run with:

    python3 scripts/test_omp_config_exporter.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from omp_config_exporter import engine  # noqa: E402
from omp_config_exporter.engine import (  # noqa: E402
    EXIT_REFUSED_APPLY,
    PLACEHOLDER_ABSOLUTE_PATH,
    PLACEHOLDER_API_KEY,
    PLACEHOLDER_BASE_URL,
    PLACEHOLDER_MODEL_ID,
    PLACEHOLDER_MODEL_NAME,
    PLACEHOLDER_PROVIDER_ID,
    PLACEHOLDER_REDACTED,
    PLACEHOLDER_THEME_NAME,
    PLACEHOLDER_THINKING_LEVEL,
    ExportPlan,
    RedactionSummary,
    RUNTIME_STATE_BASENAMES,
    RUNTIME_STATE_TOKENS,
    YAMLError,
    export_to_template,
    load_yaml,
    redact_config,
)


# --- Test fixtures ------------------------------------------------------------


#: A realistic ``config.yml`` shape, with values that look like
#: a local machine so the redaction tests can prove the placeholders
#: land everywhere they should.
SAMPLE_CONFIG_YML = """\
modelRoles:
  default: 9router/Opus
  smol: Haiku
  slow: Sonnet
  plan: Opus:xhigh
  commit: Haiku
  vision: 9router/Opus
  task: 9router/Haiku
defaultThinkingLevel: high
startup:
  quiet: false
  checkUpdate: false
retry:
  enabled: true
  maxRetries: 3
  baseDelayMs: 2000
  fallbackRevertPolicy: cooldown-expiry
compaction:
  enabled: true
  reserveTokens: 16384
  keepRecentTokens: 20000
  autoContinue: true
  strategy: context-full
skills:
  enabled: true
steeringMode: one-at-a-time
extensions:
  - ~/.omp/agent/extensions/codebase-memory-gate
interruptMode: immediate
hideThinkingBlock: false
terminal:
  showImages: true
display:
  tabWidth: 4
  showTokenUsage: true
task:
  isolation:
    mode: auto
  eager: true
  enableLsp: true
symbolPreset: nerd
theme:
  dark: titanium
  light: light
setupVersion: 1
tools:
  discoveryMode: mcp-only
mcp:
  discoveryMode: true
secrets:
  enabled: true
marketplace:
  autoUpdate: auto
dev:
  autoqa:
    consent: granted
"""

#: A realistic ``models.yml`` shape, mirroring the live
#: ``9router`` provider the local OMP install uses.
SAMPLE_MODELS_YML = """\
providers:
  9router:
    baseUrl: http://127.0.0.1:20128/v1
    apiKey: sk-5f553f4ad66fef26-ga43nj-f135962e
    api: openai-completions
    auth: apiKey
    models:
      - id: Opus
        name: Opus
        api: openai-completions
        reasoning: true
        input: [text, image]
        contextWindow: 204800
        maxTokens: 128000
      - id: Sonnet
        name: Sonnet
        api: openai-completions
        reasoning: true
        input: [text]
        contextWindow: 204800
        maxTokens: 128000
      - id: Haiku
        name: Haiku
        api: openai-completions
        reasoning: true
        input: [text, image]
        contextWindow: 204800
        maxTokens: 128000
"""

#: A second provider added on top of the live sample, so the
#: multi-provider regression test exercises unique placeholder
#: keys without depending on a particular real OMP config.
SAMPLE_SECOND_PROVIDER_YML = """\
providers:
  9router:
    baseUrl: http://127.0.0.1:20128/v1
    apiKey: sk-5f553f4ad66fef26-ga43nj-f135962e
    api: openai-completions
    auth: apiKey
    models:
      - id: Opus
        name: Opus
        api: openai-completions
        reasoning: true
        input: [text, image]
        contextWindow: 204800
        maxTokens: 128000
  openrouter:
    baseUrl: https://openrouter.example/api
    apiKey: sk-openrouter-LEAKED-KEY-001
    api: openai-completions
    auth: apiKey
    models:
      - id: gpt-5
        name: GPT5
        api: openai-completions
        reasoning: false
        input: [text]
        contextWindow: 128000
        maxTokens: 64000
  internal-router:
    baseUrl: http://internal.example/v1
    apiKey: sk-internal-DIFFERENT-KEY-002
    api: anthropic-messages
    auth: apiKey
    models:
      - id: claude-x
        name: ClaudeX
        api: anthropic-messages
        reasoning: true
        input: [text, image]
        contextWindow: 500000
        maxTokens: 32000
"""

#: Live secrets, URLs, and machine values that must NEVER appear
#: in the produced template. Used by the redaction test to grep
#: the output for the same identifiers that the live file contains.
LIVE_BANNED_LITERALS: tuple[str, ...] = (
    "sk-5f553f4ad66fef26-ga43nj-f135962e",
    "http://127.0.0.1:20128",
    "9router",
    "~/.omp/agent/extensions/codebase-memory-gate",
    "titanium",
)

#: Probe values that exercise the per-block schema whitelist and
#: the deep-scan for secret-shaped scalars. The B2 regression
#: test plants each of these somewhere in a passthrough block;
#: none of them are allowed to land in the produced text.
SECRET_PROBE_LITERALS: tuple[str, ...] = (
    "sk-admin-LEAKED",
    "sk-debug-leak",
    "sk-default-leaked",
    "internal.example.com",
    "private-registry.example.com",
    "mcp.example.com",
    "postgres://user:pass@host/db",
    "~/.omp/agent/terminal-sessions",
    "sk-leaked-in-passthrough",
)


def _seed_inputs(root: Path) -> tuple[Path, Path]:
    """Write the sample config and models files into ``root``.

    Returns ``(config_path, models_path)``. Tests use this helper
    to keep the fixture data identical across cases.
    """

    config_path = root / "config.yml"
    models_path = root / "models.yml"
    config_path.write_text(SAMPLE_CONFIG_YML, encoding="utf-8")
    models_path.write_text(SAMPLE_MODELS_YML, encoding="utf-8")
    return config_path, models_path


def _seed_secret_probe_config() -> str:
    """A config that exercises the schema whitelist and the
    secret-pattern deep scan.

    The exporter must drop unknown keys via the schema whitelist
    and replace any secret-shaped scalar that does pass the
    whitelist with :data:`PLACEHOLDER_REDACTED`. The
    ``fallbackRevertPolicy`` key below is whitelisted but has
    a secret-shaped value, so it is the one place where the
    deep-scan actually runs.
    """

    return """\
modelRoles:
  default: 9router/Opus
  smol: Haiku
  slow: Sonnet
  plan: Opus:xhigh
  commit: Haiku
  vision: 9router/Opus
  task: 9router/Haiku
defaultThinkingLevel: high
startup:
  quiet: false
  checkUpdate: false
  env:
    ADMIN_TOKEN: sk-admin-LEAKED
    LEGIT_FLAG: true
retry:
  enabled: true
  maxRetries: 3
  baseDelayMs: 2000
  fallbackRevertPolicy: sk-leaked-in-passthrough
compaction:
  enabled: true
  reserveTokens: 16384
  keepRecentTokens: 20000
  autoContinue: true
  strategy: context-full
skills:
  enabled: true
steeringMode: one-at-a-time
extensions:
  - ~/.omp/agent/extensions/codebase-memory-gate
interruptMode: immediate
hideThinkingBlock: false
terminal:
  showImages: true
  sessionDir: ~/.omp/agent/terminal-sessions
display:
  tabWidth: 4
  showTokenUsage: true
task:
  isolation:
    mode: auto
  eager: true
  enableLsp: true
  sk-leaked-in-passthrough: true
symbolPreset: nerd
theme:
  dark: titanium
  light: light
setupVersion: 1
tools:
  discoveryMode: mcp-only
  debugToken: sk-debug-leak
mcp:
  discoveryMode: true
  serverUrl: mcp.example.com
secrets:
  enabled: true
  defaultKey: sk-default-leaked
marketplace:
  autoUpdate: auto
  registryUrl: private-registry.example.com
dev:
  autoqa:
    consent: granted
  rogue:
    secret: sk-leaked-in-passthrough
  db:
    connection: postgres://user:pass@host/db
"""


# --- YAML loader tests --------------------------------------------------------


class LoadYamlTest(unittest.TestCase):
    """The loader handles the OMP runtime's block-style subset."""

    def test_parses_sample_config(self) -> None:
        parsed = load_yaml(SAMPLE_CONFIG_YML)
        self.assertIsInstance(parsed, dict)
        # Spot-check a few top-level keys and nested values.
        self.assertEqual(parsed["defaultThinkingLevel"], "high")
        self.assertEqual(parsed["modelRoles"]["default"], "9router/Opus")
        self.assertEqual(parsed["theme"]["dark"], "titanium")
        self.assertEqual(
            parsed["extensions"],
            ["~/.omp/agent/extensions/codebase-memory-gate"],
        )
        self.assertEqual(parsed["retry"]["maxRetries"], 3)
        self.assertEqual(parsed["startup"]["quiet"], False)
        self.assertEqual(parsed["compaction"]["enabled"], True)

    def test_parses_inline_mapping_sequence(self) -> None:
        parsed = load_yaml(SAMPLE_MODELS_YML)
        self.assertIn("providers", parsed)
        models = parsed["providers"]["9router"]["models"]
        # The OMP runtime's ``- id: Opus / name: Opus`` style
        # produces a list of mappings, not a list of single-key
        # dicts. A previous bug returned each model twice; this
        # test pins the expected count and the per-model shape.
        self.assertEqual(len(models), 3)
        for entry in models:
            self.assertIsInstance(entry, dict)
            self.assertIn("id", entry)
            self.assertIn("name", entry)
            self.assertIn("contextWindow", entry)
        # Numeric fields come through as ints, not strings.
        self.assertEqual(models[0]["contextWindow"], 204800)
        self.assertEqual(models[0]["maxTokens"], 128000)

    def test_tab_character_is_rejected(self) -> None:
        with self.assertRaises(YAMLError) as ctx:
            load_yaml("modelRoles:\n\tdefault: Opus\n")
        self.assertIn("tab", str(ctx.exception))

    def test_over_indent_in_mapping_raises(self) -> None:
        with self.assertRaises(YAMLError):
            load_yaml("outer:\n    inner: 1\n  sibling: 2\n")

    def test_empty_input_returns_empty_dict(self) -> None:
        self.assertEqual(load_yaml(""), {})
        self.assertEqual(load_yaml("# comment only\n"), {})

    def test_top_level_must_start_at_column_zero(self) -> None:
        with self.assertRaises(YAMLError):
            load_yaml("  outer: 1\n")


# --- Redaction tests ----------------------------------------------------------


class RedactionConfigTest(unittest.TestCase):
    """``redact_config`` swaps every machine-specific value."""

    def _summary(self) -> RedactionSummary:
        return RedactionSummary()

    def test_model_roles_are_replaced_with_placeholder(self) -> None:
        summary = self._summary()
        config = load_yaml(SAMPLE_CONFIG_YML)
        out = redact_config(config, summary)
        self.assertEqual(out["modelRoles"]["default"], PLACEHOLDER_MODEL_ID)
        self.assertEqual(out["modelRoles"]["smol"], PLACEHOLDER_MODEL_ID)
        # One redaction per role key, not per slash.
        self.assertEqual(summary.model_ids, 7)

    def test_thinking_level_is_replaced(self) -> None:
        summary = self._summary()
        config = load_yaml(SAMPLE_CONFIG_YML)
        out = redact_config(config, summary)
        self.assertEqual(
            out["defaultThinkingLevel"], PLACEHOLDER_THINKING_LEVEL
        )
        self.assertEqual(summary.thinking_levels, 1)

    def test_theme_names_are_replaced(self) -> None:
        summary = self._summary()
        config = load_yaml(SAMPLE_CONFIG_YML)
        out = redact_config(config, summary)
        self.assertEqual(out["theme"]["dark"], PLACEHOLDER_THEME_NAME)
        self.assertEqual(out["theme"]["light"], PLACEHOLDER_THEME_NAME)
        self.assertEqual(summary.theme_names, 2)

    def test_extension_path_is_replaced(self) -> None:
        summary = self._summary()
        config = load_yaml(SAMPLE_CONFIG_YML)
        out = redact_config(config, summary)
        self.assertEqual(
            out["extensions"]["load_paths"], [PLACEHOLDER_ABSOLUTE_PATH]
        )
        self.assertEqual(summary.absolute_paths, 1)

    def test_passthrough_fields_are_preserved(self) -> None:
        # The redaction must not touch fields that are not
        # machine-specific. The committed template documents
        # them as local policy choices, so the live values are
        # safe to copy.
        config = load_yaml(SAMPLE_CONFIG_YML)
        out = redact_config(config, RedactionSummary())
        self.assertEqual(out["retry"]["maxRetries"], 3)
        self.assertEqual(out["retry"]["baseDelayMs"], 2000)
        self.assertEqual(out["compaction"]["strategy"], "context-full")
        self.assertEqual(out["skills"]["enabled"], True)


class RedactionProvidersTest(unittest.TestCase):
    """``_redact_providers_block`` swaps credentials and IDs."""

    def test_base_url_and_api_key_are_redacted(self) -> None:
        summary = RedactionSummary()
        providers = load_yaml(SAMPLE_MODELS_YML)["providers"]
        out = engine._redact_providers_block(providers, summary)
        # The single provider is keyed by the placeholder.
        self.assertIn(PLACEHOLDER_PROVIDER_ID, out)
        entry = out[PLACEHOLDER_PROVIDER_ID]
        self.assertEqual(entry["baseUrl"], PLACEHOLDER_BASE_URL)
        self.assertEqual(entry["apiKey"], PLACEHOLDER_API_KEY)
        # Protocol fields are kept so the user can see which
        # API family the provider used.
        self.assertEqual(entry["api"], "openai-completions")
        self.assertEqual(entry["auth"], "apiKey")
        # Models are present, with id/name redacted and
        # contextWindow/maxTokens preserved.
        self.assertEqual(len(entry["models"]), 3)
        for m in entry["models"]:
            self.assertEqual(m["id"], PLACEHOLDER_MODEL_ID)
            self.assertEqual(m["name"], PLACEHOLDER_MODEL_NAME)
            self.assertEqual(m["contextWindow"], 204800)
            self.assertEqual(m["maxTokens"], 128000)
        self.assertEqual(summary.base_urls, 1)
        self.assertEqual(summary.api_keys, 1)
        self.assertEqual(summary.provider_ids, 1)
        self.assertEqual(summary.provider_blocks_redacted, 1)
        # 3 model ids + 3 model names per provider.
        self.assertEqual(summary.model_ids, 3)
        self.assertEqual(summary.model_names, 3)

    def test_multi_provider_emits_unique_placeholder_keys(self) -> None:
        # Regression test for B1: previously every provider
        # was written under the same ``<provider-id>`` key, so
        # the second provider clobbered the first. Three input
        # providers must produce three output entries keyed by
        # three different placeholders, and every distinct
        # api/auth value from the input must survive in the
        # output.
        summary = RedactionSummary()
        providers = load_yaml(SAMPLE_SECOND_PROVIDER_YML)["providers"]
        self.assertEqual(len(providers), 3)
        out = engine._redact_providers_block(providers, summary)

        # First provider keeps the unsuffixed placeholder;
        # subsequent ones are numbered.
        self.assertIn("<provider-id>", out)
        self.assertIn("<provider-id-2>", out)
        self.assertIn("<provider-id-3>", out)
        self.assertEqual(len(out), 3)

        # Summary counts honestly reflect three providers, not
        # one. ``provider_ids`` and ``provider_blocks_redacted``
        # both increment once per provider in the input.
        self.assertEqual(summary.provider_ids, 3)
        self.assertEqual(summary.provider_blocks_redacted, 3)

        # The first block's protocol markers must survive (so
        # the user can see which API family each provider used)
        # and the second/third blocks' distinct auth/api values
        # must also survive, proving the providers did not
        # clobber each other.
        out_apis = [out[key]["api"] for key in (
            "<provider-id>", "<provider-id-2>", "<provider-id-3>"
        )]
        out_auths = [out[key]["auth"] for key in (
            "<provider-id>", "<provider-id-2>", "<provider-id-3>"
        )]
        self.assertIn("openai-completions", out_apis)
        self.assertIn("anthropic-messages", out_apis)
        self.assertEqual(out_auths.count("apiKey"), 3)

        # Three base URLs and three API keys are redacted.
        self.assertEqual(summary.base_urls, 3)
        self.assertEqual(summary.api_keys, 3)


# --- B2: secret-shaped passthrough regression ---------------------------------


class SecretPassthroughRedactionTest(unittest.TestCase):
    """Per-block schema whitelist + deep-scan keep secrets out of output."""

    def test_secret_probes_never_appear_in_produced_text(self) -> None:
        # Regression test for B2. The probe config plants each
        # secret-shaped value somewhere in a passthrough block;
        # none of them are allowed to land in the produced text.
        config = load_yaml(_seed_secret_probe_config())
        summary = RedactionSummary()
        out_text = json.dumps(
            redact_config(config, summary), indent=2, sort_keys=False
        )
        for probe in SECRET_PROBE_LITERALS:
            self.assertNotIn(
                probe,
                out_text,
                f"secret probe {probe!r} leaked into produced text",
            )
        # The whitelist did record drops; some unknown keys
        # are counted under ``unknown_passthrough_dropped``.
        self.assertGreater(summary.unknown_passthrough_dropped, 0)
        # Whitelisted, non-secret scalars still pass through.
        # Spot-check a handful of allowed values that must
        # still be present after redaction.
        self.assertIn("context-full", out_text)
        self.assertIn("one-at-a-time", out_text)
        self.assertIn("mcp-only", out_text)
        # ``retry.fallbackRevertPolicy`` is whitelisted but had
        # a secret-shaped value; the deep scan replaces it
        # with the redacted placeholder rather than copying it
        # through.
        self.assertIn(PLACEHOLDER_REDACTED, out_text)

    def test_unknown_passthrough_keys_are_dropped(self) -> None:
        # The whitelist is closed: keys not enumerated in
        # BLOCK_SCHEMAS (and not sub-keys of an enumerated
        # block) are dropped. ``dev.rogue`` and ``dev.db`` are
        # not in the whitelist; their sub-keys must not land
        # in the produced text.
        config = load_yaml(_seed_secret_probe_config())
        out = redact_config(config, RedactionSummary())
        dev_block = out.get("dev", {})
        self.assertNotIn("rogue", dev_block)
        self.assertNotIn("db", dev_block)
        # ``dev.autoqa.consent`` is whitelisted and must pass
        # through.
        self.assertEqual(dev_block.get("autoqa", {}).get("consent"), "granted")
        # ``task.sk-leaked-in-passthrough`` is not a whitelisted
        # sub-key of ``task``; it must be dropped.
        self.assertNotIn("sk-leaked-in-passthrough", out.get("task", {}))
        # ``mcp.serverUrl`` is not a whitelisted sub-key.
        self.assertNotIn("serverUrl", out.get("mcp", {}))
        # ``tools.debugToken`` is not whitelisted.
        self.assertNotIn("debugToken", out.get("tools", {}))

    def test_known_passthrough_values_remain_after_drop(self) -> None:
        # Sanity: the schema filter must not erase the
        # machine-neutral values the committed template
        # documents as policy. After filtering, the usual
        # policy fields are still present and unchanged.
        config = load_yaml(_seed_secret_probe_config())
        out = redact_config(config, RedactionSummary())
        self.assertEqual(out["retry"]["maxRetries"], 3)
        self.assertEqual(out["compaction"]["strategy"], "context-full")
        self.assertEqual(out["skills"]["enabled"], True)
        self.assertEqual(out["task"]["isolation"]["mode"], "auto")
        self.assertEqual(out["task"]["eager"], True)
        self.assertEqual(out["task"]["enableLsp"], True)


# --- Plan construction tests --------------------------------------------------


class ExportPlanTest(unittest.TestCase):
    """``export_to_template`` produces a plan with the right shape."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        self.config_path, self.models_path = _seed_inputs(self.tmp_path)
        self.output_path = self.tmp_path / "out" / "template.json"

    def test_plan_produces_redacted_template(self) -> None:
        plan = export_to_template(
            config_path=self.config_path,
            models_path=self.models_path,
            output_path=self.output_path,
        )
        self.assertTrue(plan.config_loaded)
        self.assertTrue(plan.models_loaded)
        self.assertEqual(plan.refused_inputs, [])
        self.assertIsNotNone(plan.produced_template)
        self.assertIsNotNone(plan.produced_text)

        produced = json.loads(plan.produced_text)
        # Live literals must never appear in the produced text.
        for banned in LIVE_BANNED_LITERALS:
            self.assertNotIn(
                banned,
                plan.produced_text,
                f"live literal {banned!r} leaked into output",
            )
        # Sanity-check the produced shape matches the committed
        # template's top-level conventions.
        self.assertIn("modelRoles", produced)
        self.assertIn("providers", produced)
        self.assertIn("runtimes", produced)
        self.assertIn("inheritance", produced)
        self.assertIn("orchestration", produced)
        self.assertIn("env", produced)

    def test_redaction_summary_covers_every_category(self) -> None:
        plan = export_to_template(
            config_path=self.config_path,
            models_path=self.models_path,
            output_path=self.output_path,
        )
        counts = plan.redactions.as_dict()
        self.assertGreater(counts["api_keys"], 0)
        self.assertGreater(counts["base_urls"], 0)
        self.assertGreater(counts["provider_ids"], 0)
        self.assertGreater(counts["model_ids"], 0)
        self.assertGreater(counts["model_names"], 0)
        self.assertGreater(counts["absolute_paths"], 0)
        self.assertGreater(counts["thinking_levels"], 0)
        self.assertGreater(counts["theme_names"], 0)
        self.assertEqual(
            counts["providers_dropped"], 0,
            "providers block was dropped entirely; the export should "
            "keep the shape with placeholders",
        )

    def test_no_secrets_in_produced_text(self) -> None:
        plan = export_to_template(
            config_path=self.config_path,
            models_path=self.models_path,
            output_path=self.output_path,
        )
        # Belt-and-braces check: the live OMP install's
        # ``apiKey`` prefix and base-URL hostname must not
        # survive the redaction.
        self.assertNotIn("sk-", plan.produced_text)
        self.assertNotIn("127.0.0.1", plan.produced_text)
        self.assertNotIn(".omp/agent", plan.produced_text)


class MissingFileTest(unittest.TestCase):
    """A missing input is recorded on the plan, not raised."""

    def test_missing_config_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _, models_path = _seed_inputs(tmp_path)
            plan = export_to_template(
                config_path=tmp_path / "no-such-config.yml",
                models_path=models_path,
                output_path=tmp_path / "out.json.template",
            )
            self.assertFalse(plan.config_loaded)
            self.assertTrue(plan.models_loaded)
            # The refusal is recorded with a clear reason.
            self.assertEqual(len(plan.refused_inputs), 1)
            refused_path, reason = plan.refused_inputs[0]
            self.assertTrue(str(refused_path).endswith("no-such-config.yml"))
            self.assertIn("not found", reason.lower())
            # The plan still produces a template because the
            # models file is enough on its own.
            self.assertIsNotNone(plan.produced_template)

    def test_missing_models_with_allow_missing_keeps_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path, _ = _seed_inputs(tmp_path)
            plan = export_to_template(
                config_path=config_path,
                models_path=tmp_path / "no-such-models.yml",
                output_path=tmp_path / "out.json.template",
                allow_missing_models=True,
            )
            self.assertTrue(plan.config_loaded)
            self.assertFalse(plan.models_loaded)
            self.assertEqual(plan.refused_inputs, [])
            self.assertIsNotNone(plan.produced_template)

    def test_both_missing_yields_empty_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Default flags: missing config is refused,
            # missing models is silently skipped. The plan
            # should still come back empty because no input
            # could be loaded.
            plan = export_to_template(
                config_path=tmp_path / "no-config.yml",
                models_path=tmp_path / "no-models.yml",
                output_path=tmp_path / "out.json.template",
            )
            self.assertIsNone(plan.produced_template)
            self.assertEqual(len(plan.refused_inputs), 1)
            refused_path, _ = plan.refused_inputs[0]
            self.assertTrue(str(refused_path).endswith("no-config.yml"))

    def test_both_missing_with_require_models_yields_two_refusals(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plan = export_to_template(
                config_path=tmp_path / "no-config.yml",
                models_path=tmp_path / "no-models.yml",
                output_path=tmp_path / "out.json.template",
                allow_missing_config=False,
                allow_missing_models=False,
            )
            self.assertIsNone(plan.produced_template)
            self.assertEqual(len(plan.refused_inputs), 2)


class RuntimeStateRefusalTest(unittest.TestCase):
    """Live runtime state files are refused up front."""

    def test_agent_db_path_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bad = tmp_path / "agent.db"
            bad.write_text("BINARY", encoding="utf-8")
            plan = export_to_template(
                config_path=bad,
                models_path=tmp_path / "models.yml",
                output_path=tmp_path / "out.json.template",
            )
            self.assertFalse(plan.config_loaded)
            self.assertEqual(len(plan.refused_inputs), 1)
            _, reason = plan.refused_inputs[0]
            self.assertIn("live runtime state", reason)

    def test_sessions_dir_path_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bad = tmp_path / "sessions" / "live.yml"
            bad.parent.mkdir()
            bad.write_text("key: value\n", encoding="utf-8")
            plan = export_to_template(
                config_path=bad,
                models_path=tmp_path / "models.yml",
                output_path=tmp_path / "out.json.template",
            )
            self.assertFalse(plan.config_loaded)
            self.assertEqual(len(plan.refused_inputs), 1)
            _, reason = plan.refused_inputs[0]
            self.assertIn("live runtime state", reason)

    def test_terminal_sessions_dir_path_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bad = tmp_path / "terminal-sessions" / "t1.yml"
            bad.parent.mkdir()
            bad.write_text("key: value\n", encoding="utf-8")
            plan = export_to_template(
                config_path=bad,
                models_path=tmp_path / "models.yml",
                output_path=tmp_path / "out.json.template",
            )
            self.assertFalse(plan.config_loaded)
            self.assertEqual(len(plan.refused_inputs), 1)

    def test_runtime_state_tokens_include_db_and_sessions(self) -> None:
        # Lock the public contract: a future change that drops
        # one of these tokens is a regression, not a refactor.
        for token in (
            "sessions",
            "session",
            "terminal-sessions",
            "cache",
            "logs",
            "log",
            "history",
            "histories",
            "audit",
            "natives",
            "native",
            "install-id",
            "state",
            "runtime",
            "db",
        ):
            self.assertIn(token, RUNTIME_STATE_TOKENS)

    def test_runtime_state_basenames_include_db_files(self) -> None:
        for name in (
            "agent.db",
            "history.db",
            "models.db",
            "autoqa.db",
            "codebase-memory-mcp-omp-proxy.mjs",
        ):
            self.assertIn(name, RUNTIME_STATE_BASENAMES)


class WritePlanTest(unittest.TestCase):
    """The write path is safe by default and respects --force."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        self.config_path, self.models_path = _seed_inputs(self.tmp_path)
        self.output_path = self.tmp_path / "out.json.template"

    def test_write_plan_creates_file(self) -> None:
        plan = export_to_template(
            config_path=self.config_path,
            models_path=self.models_path,
            output_path=self.output_path,
        )
        engine._write_plan(plan)
        self.assertTrue(self.output_path.is_file())
        # The output is a JSON object, not the live values.
        with self.output_path.open(encoding="utf-8") as fh:
            text = fh.read()
        for banned in LIVE_BANNED_LITERALS:
            self.assertNotIn(banned, text)

    def test_write_plan_refuses_to_overwrite_by_default(self) -> None:
        self.output_path.write_text("EXISTING CONTENT\n", encoding="utf-8")
        plan = export_to_template(
            config_path=self.config_path,
            models_path=self.models_path,
            output_path=self.output_path,
        )
        with self.assertRaises(FileExistsError):
            engine._write_plan(plan)
        # Original content is preserved.
        self.assertEqual(
            self.output_path.read_text(encoding="utf-8"),
            "EXISTING CONTENT\n",
        )

    def test_write_plan_with_force_overwrites(self) -> None:
        self.output_path.write_text("EXISTING CONTENT\n", encoding="utf-8")
        plan = export_to_template(
            config_path=self.config_path,
            models_path=self.models_path,
            output_path=self.output_path,
        )
        engine._write_plan(plan, force=True)
        self.assertTrue(self.output_path.is_file())
        self.assertNotEqual(
            self.output_path.read_text(encoding="utf-8"),
            "EXISTING CONTENT\n",
        )


# --- CLI tests ---------------------------------------------------------------


class CliDryRunTest(unittest.TestCase):
    """The CLI is read-only by default."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        self.config_path, self.models_path = _seed_inputs(self.tmp_path)
        self.output_path = self.tmp_path / "out.json.template"

    def _run(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "export_omp_config.py"),
                "--config",
                str(self.config_path),
                "--models",
                str(self.models_path),
                "--output",
                str(self.output_path),
                "--repo",
                str(REPO_ROOT),
                *extra,
            ],
            capture_output=True,
            text=True,
        )

    def test_dry_run_does_not_create_output(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[dry-run]", result.stdout)
        self.assertIn("REDACT", result.stdout)
        self.assertFalse(
            self.output_path.exists(),
            f"dry-run must not create {self.output_path}",
        )

    def test_apply_writes_output(self) -> None:
        result = self._run("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[apply]", result.stdout)
        self.assertTrue(self.output_path.is_file())
        # Live literals must not be in the written file.
        text = self.output_path.read_text(encoding="utf-8")
        for banned in LIVE_BANNED_LITERALS:
            self.assertNotIn(banned, text)

    def test_apply_refuses_to_overwrite_existing(self) -> None:
        self.output_path.write_text("EXISTING\n", encoding="utf-8")
        result = self._run("--apply")
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("refusing to overwrite", result.stderr)
        self.assertEqual(
            self.output_path.read_text(encoding="utf-8"), "EXISTING\n"
        )

    def test_apply_force_overwrites(self) -> None:
        self.output_path.write_text("EXISTING\n", encoding="utf-8")
        result = self._run("--apply", "--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(
            self.output_path.read_text(encoding="utf-8"), "EXISTING\n"
        )

    def test_dry_run_summary_includes_redaction_count(self) -> None:
        result = self._run()
        self.assertIn("redactions=", result.stdout)


class CliRuntimeStateRefusalTest(unittest.TestCase):
    """The CLI refuses live runtime state paths up front."""

    def test_agent_db_input_is_refused_in_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bad = tmp_path / "agent.db"
            bad.write_text("BIN", encoding="utf-8")
            # Provide a real models.yml so the plan still has
            # something to summarize. The config refusal is
            # what we are testing.
            (tmp_path / "models.yml").write_text(
                SAMPLE_MODELS_YML, encoding="utf-8"
            )
            output_path = tmp_path / "out.json.template"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "export_omp_config.py"),
                    "--config",
                    str(bad),
                    "--models",
                    str(tmp_path / "models.yml"),
                    "--output",
                    str(output_path),
                    "--repo",
                    str(REPO_ROOT),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("REFUSE", result.stdout)
            self.assertIn("agent.db", result.stdout)
            # Plan still produced a template from models.yml.
            self.assertIn("WRITE", result.stdout)
            self.assertFalse(
                output_path.exists(),
                "dry-run must not create output even when one input "
                "is refused",
            )


# --- B3: --apply with refused input must not write ---------------------------


class ApplyRefusedInputTest(unittest.TestCase):
    """``--apply`` together with a refused input must abort and not write."""

    def test_apply_with_refused_input_returns_nonzero(self) -> None:
        # Regression test for B3. Pointing --config at a live
        # runtime-state path (agent.db) produces a refused
        # input. ``--apply`` must return non-zero (status 4)
        # and must not create the output file.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bad = tmp_path / "agent.db"
            bad.write_text("BIN", encoding="utf-8")
            (tmp_path / "models.yml").write_text(
                SAMPLE_MODELS_YML, encoding="utf-8"
            )
            output_path = tmp_path / "out.json.template"
            output_path.write_text("SENTINEL\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "export_omp_config.py"),
                    "--config",
                    str(bad),
                    "--models",
                    str(tmp_path / "models.yml"),
                    "--output",
                    str(output_path),
                    "--repo",
                    str(REPO_ROOT),
                    "--apply",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode, EXIT_REFUSED_APPLY, result.stderr
            )
            self.assertNotEqual(result.returncode, 0)
            # The output file is untouched. The sentinel
            # written before the run must still be there.
            self.assertEqual(
                output_path.read_text(encoding="utf-8"), "SENTINEL\n"
            )

    def test_apply_with_missing_models_refused_returns_nonzero(self) -> None:
        # ``--require-models`` together with a missing
        # ``--models`` file is the canonical refused-input
        # case from the README. ``--apply`` must abort.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path, _ = _seed_inputs(tmp_path)
            output_path = tmp_path / "out.json.template"
            output_path.write_text("SENTINEL\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "export_omp_config.py"),
                    "--config",
                    str(config_path),
                    "--models",
                    str(tmp_path / "no-models.yml"),
                    "--output",
                    str(output_path),
                    "--repo",
                    str(REPO_ROOT),
                    "--require-models",
                    "--apply",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode, EXIT_REFUSED_APPLY, result.stderr
            )
            self.assertEqual(
                output_path.read_text(encoding="utf-8"), "SENTINEL\n"
            )

    def test_dry_run_with_refused_input_still_returns_zero(self) -> None:
        # Dry-run is read-only and prints the plan. Even with
        # refused inputs, dry-run must still return 0 so users
        # can inspect the refusal without it being a hard
        # failure for CI.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bad = tmp_path / "agent.db"
            bad.write_text("BIN", encoding="utf-8")
            (tmp_path / "models.yml").write_text(
                SAMPLE_MODELS_YML, encoding="utf-8"
            )
            output_path = tmp_path / "out.json.template"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "export_omp_config.py"),
                    "--config",
                    str(bad),
                    "--models",
                    str(tmp_path / "models.yml"),
                    "--output",
                    str(output_path),
                    "--repo",
                    str(REPO_ROOT),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("REFUSE", result.stdout)


# --- Public API surface ------------------------------------------------------


class PublicApiTest(unittest.TestCase):
    """The package's ``__all__`` is the contract for library callers."""

    def test_engine_exports_match_init(self) -> None:
        from omp_config_exporter import __all__ as exported
        for name in (
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
        ):
            self.assertIn(name, exported)
            self.assertTrue(
                hasattr(engine, name),
                f"omp_config_exporter.engine.{name} missing",
            )


if __name__ == "__main__":
    quiet = os.environ.get("OMP_EXPORTER_QUIET") == "1"
    unittest.main(
        module=__name__,
        argv=["__main__"] + ([] if quiet else ["-v"]),
        verbosity=1 if quiet else 2,
        exit=True,
    )
