#!/usr/bin/env python3
"""Tests for `scripts/validate_repo_structure.py`.

These tests build tiny temporary repository trees that exercise each
architectural-boundary rule the validator enforces. Each test seeds a
fixture, runs `run()` against it, and asserts the expected failures
appear (or, for the positive case, that no failures appear).

Run with:

    python3 scripts/test_validate_repo_structure.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Iterable

# Make the validator importable regardless of the test invocation cwd.
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate_repo_structure as vrs  # noqa: E402


def _make_root() -> "tempfile.TemporaryDirectory[str]":
    """Return a TemporaryDirectory pre-populated with the baseline structure."""
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    # Top-level areas.
    for area in vrs.REQUIRED_TOP_LEVEL_AREAS:
        (root / area).mkdir()
    (root / "docs" / "maintenance").mkdir(parents=True)
    # Asset categories.
    for cat in vrs.ALLOWED_ASSET_CATEGORIES:
        (root / "assets" / cat).mkdir(parents=True)
    # Runtime targets with the expected templates.
    for target, spec in vrs.TARGET_TEMPLATES.items():
        target_dir = root / "targets" / target
        target_dir.mkdir(parents=True)
        for template in spec["templates"]:
            (target_dir / template).write_text("# template\n")
    # Stash the path on the handle so callers can use it.
    tmp.root_path = root  # type: ignore[attr-defined]
    return tmp


def _write(path: Path, content: str = "# note\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _boundaries(failures: Iterable[vrs.Failure]) -> set[str]:
    return {f.boundary for f in failures}


def _details(failures: Iterable[vrs.Failure]) -> list[str]:
    return [f.detail for f in failures]


class BaselinePassesTest(unittest.TestCase):
    """A freshly-built compliant fixture should produce zero failures."""

    def test_baseline_passes(self) -> None:
        tmp = _make_root()
        try:
            failures = vrs.run(tmp.root_path)  # type: ignore[attr-defined]
            self.assertEqual(
                failures,
                [],
                f"expected no failures, got: {[(f.boundary, f.detail) for f in failures]}",
            )
        finally:
            tmp.cleanup()


class TopLevelAreaTest(unittest.TestCase):
    def test_missing_top_level_area_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            # Remove one required top-level area.
            (root / "inbox").rmdir()
            failures = vrs.run(root)
            self.assertIn("top-level area", _boundaries(failures))
            self.assertTrue(
                any("inbox" in d for d in _details(failures)),
                f"expected 'inbox' in details, got: {_details(failures)}",
            )
        finally:
            tmp.cleanup()

    def test_missing_maintenance_area_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            (root / "docs" / "maintenance").rmdir()
            failures = vrs.run(root)
            self.assertIn("maintenance area", _boundaries(failures))
        finally:
            tmp.cleanup()


class AssetCategoryTest(unittest.TestCase):
    def test_unknown_asset_category_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            _write(root / "assets" / "snippets" / "README.md")
            failures = vrs.run(root)
            self.assertIn("asset category whitelist", _boundaries(failures))
            self.assertTrue(
                any("snippets" in d for d in _details(failures)),
                f"expected 'snippets' in details, got: {_details(failures)}",
            )
        finally:
            tmp.cleanup()

    def test_forbidden_commands_dir_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            _write(root / "assets" / "commands" / "review.md")
            failures = vrs.run(root)
            self.assertIn("forbidden shared asset dir", _boundaries(failures))
        finally:
            tmp.cleanup()

    def test_forbidden_prompts_dir_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            _write(root / "assets" / "prompts" / "draft.md")
            failures = vrs.run(root)
            self.assertIn("forbidden shared asset dir", _boundaries(failures))
        finally:
            tmp.cleanup()

    def test_forbidden_tips_dir_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            _write(root / "assets" / "tips" / "speed.md")
            failures = vrs.run(root)
            self.assertIn("forbidden shared asset dir", _boundaries(failures))
        finally:
            tmp.cleanup()


class TargetTemplateTest(unittest.TestCase):
    def test_missing_target_dir_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            # Delete the claude-code landing area entirely; the validator
            # must surface a 'target landing area' failure naming the
            # missing path even when the rest of the tree is compliant.
            import shutil

            shutil.rmtree(root / "targets" / "claude-code")
            failures = vrs.run(root)
            self.assertIn("target landing area", _boundaries(failures))
            self.assertTrue(
                any(
                    "targets/claude-code" in d
                    and "claude-code" in d
                    for d in _details(failures)
                ),
                f"expected missing targets/claude-code in details, got: {_details(failures)}",
            )
        finally:
            tmp.cleanup()

    def test_missing_template_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            (root / "targets" / "claude-code" / "settings.json.template").unlink()
            failures = vrs.run(root)
            self.assertIn("target template config", _boundaries(failures))
        finally:
            tmp.cleanup()

    def test_live_sensitive_claude_settings_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            _write(
                root / "targets" / "claude-code" / "settings.json",
                '{"model": "leaked"}',
            )
            failures = vrs.run(root)
            self.assertIn("live sensitive config", _boundaries(failures))
        finally:
            tmp.cleanup()

    def test_live_mcp_json_for_claude_code_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            _write(
                root / "targets" / "claude-code" / "mcp.json",
                '{"mcpServers": {}}',
            )
            failures = vrs.run(root)
            self.assertIn("live sensitive config", _boundaries(failures))
        finally:
            tmp.cleanup()

    def test_live_codex_config_toml_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            _write(
                root / "targets" / "codex" / "config.toml",
                "[model]\ndefault = \"leaked\"\n",
            )
            failures = vrs.run(root)
            self.assertIn("live sensitive config", _boundaries(failures))
        finally:
            tmp.cleanup()

    def test_live_oh_my_pi_config_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            _write(
                root / "targets" / "oh-my-pi" / "omp.config.json",
                '{"model": "leaked"}',
            )
            failures = vrs.run(root)
            self.assertIn("live sensitive config", _boundaries(failures))
        finally:
            tmp.cleanup()


class SharedMcpAssetTest(unittest.TestCase):
    def test_json_card_in_shared_mcp_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            _write(
                root / "assets" / "mcp-servers" / "github.json",
                '{"command": "gh"}',
            )
            failures = vrs.run(root)
            self.assertIn("shared MCP asset shape", _boundaries(failures))
        finally:
            tmp.cleanup()

    def test_toml_card_in_shared_mcp_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            _write(
                root / "assets" / "mcp-servers" / "github.toml",
                '[server]\ncommand = "gh"\n',
            )
            failures = vrs.run(root)
            self.assertIn("shared MCP asset shape", _boundaries(failures))
        finally:
            tmp.cleanup()

    def test_yaml_card_in_shared_mcp_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            _write(
                root / "assets" / "mcp-servers" / "github.yaml",
                "command: gh\n",
            )
            failures = vrs.run(root)
            self.assertIn("shared MCP asset shape", _boundaries(failures))
        finally:
            tmp.cleanup()

    def test_markdown_card_in_shared_mcp_is_allowed(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            _write(
                root / "assets" / "mcp-servers" / "github.md",
                "# github MCP server card\n",
            )
            failures = vrs.run(root)
            self.assertNotIn("shared MCP asset shape", _boundaries(failures))
        finally:
            tmp.cleanup()


class SharedHookAssetTest(unittest.TestCase):
    def test_executable_script_in_shared_hooks_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            _write(
                root / "assets" / "hooks" / "pre-tool.sh",
                "#!/usr/bin/env bash\necho hook\n",
            )
            failures = vrs.run(root)
            self.assertIn("shared hook asset shape", _boundaries(failures))
        finally:
            tmp.cleanup()

    def test_python_script_in_shared_hooks_is_reported(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            _write(
                root / "assets" / "hooks" / "policy.py",
                "def hook():\n    return None\n",
            )
            failures = vrs.run(root)
            self.assertIn("shared hook asset shape", _boundaries(failures))
        finally:
            tmp.cleanup()

    def test_markdown_policy_note_in_shared_hooks_is_allowed(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            _write(
                root / "assets" / "hooks" / "pre-tool-use.md",
                "# PreToolUse policy\n",
            )
            failures = vrs.run(root)
            self.assertNotIn("shared hook asset shape", _boundaries(failures))
        finally:
            tmp.cleanup()



class SeededExampleAssetsTest(unittest.TestCase):
    """The example files seeded for issue #7 must stay inside the
    agreed asset shape: markdown only, one per reusable category, and
    never copied into a forbidden shared asset directory.

    These guards exist so a future refactor (renaming an example to a
    runtime-native config format, moving it into `assets/commands/`,
    etc.) is caught by a unit test rather than by a human review.
    """

    EXPECTED_EXAMPLES: tuple[tuple[str, str], ...] = (
        ("skills", "example-repo-triage.md"),
        ("agents", "example-code-reviewer.md"),
        ("mcp-servers", "example-github.md"),
        ("hooks", "example-pre-tool-use-block-secret-writes.md"),
        ("rules", "example-boundary-respect.md"),
        ("packs", "example-triage-pack.md"),
    )

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    def test_one_example_per_agreed_asset_category(self) -> None:
        root = self._repo_root()
        missing: list[str] = []
        for category, filename in self.EXPECTED_EXAMPLES:
            path = root / "assets" / category / filename
            if not path.is_file():
                missing.append(str(path.relative_to(root)))
        self.assertEqual(
            missing,
            [],
            f"missing seed examples: {missing}",
        )

    def test_seed_examples_are_markdown_only(self) -> None:
        root = self._repo_root()
        offenders: list[str] = []
        for category, _filename in self.EXPECTED_EXAMPLES:
            cat_dir = root / "assets" / category
            for entry in sorted(cat_dir.iterdir()):
                if entry.name.startswith("."):
                    continue
                if entry.suffix.lower() != ".md":
                    offenders.append(
                        str(entry.relative_to(root))
                    )
        self.assertEqual(
            offenders,
            [],
            f"seed examples must stay .md, found runtime-native shapes: {offenders}",
        )

    def test_seed_examples_satisfy_validator(self) -> None:
        """The seed files must not regress the structure validator."""
        root = self._repo_root()
        failures = vrs.run(root)
        self.assertEqual(
            failures,
            [],
            f"validator regressions: {[(f.boundary, f.detail) for f in failures]}",
        )

    def test_seed_examples_do_not_inline_other_assets(self) -> None:
        """A pack or role blueprint must link to other assets; it
        must not inline the full body of another example, which would
        turn the pack into a copy and break the link-only rule.
        """
        root = self._repo_root()
        offenders: list[str] = []
        for category, filename in self.EXPECTED_EXAMPLES:
            asset_path = root / "assets" / category / filename
            asset_text = asset_path.read_text()
            for other_category, other_filename in self.EXPECTED_EXAMPLES:
                if (other_category, other_filename) == (category, filename):
                    continue
                target_path = root / "assets" / other_category / other_filename
                if not target_path.is_file():
                    continue
                target_text = target_path.read_text()
                # Cross-references by relative path are the whole point
                # of the pack category. We only guard against full-body
                # duplication, which would mean the pack owns the
                # content instead of linking to it.
                if len(target_text) > 200 and target_text in asset_text:
                    offenders.append(
                        f"{asset_path.relative_to(root)} appears to "
                        f"inline {target_path.relative_to(root)}"
                    )
        self.assertEqual(
            offenders,
            [],
            f"pack/example inlining detected: {offenders}",
        )




class ExitCodeTest(unittest.TestCase):
    """The CLI entry point must surface failures via process exit code."""

    def test_main_returns_zero_on_clean_tree(self) -> None:
        tmp = _make_root()
        try:
            exit_code = vrs.main(["--root", str(tmp.root_path)])  # type: ignore[attr-defined]
            self.assertEqual(exit_code, 0)
        finally:
            tmp.cleanup()

    def test_main_returns_nonzero_on_violations(self) -> None:
        tmp = _make_root()
        try:
            root = tmp.root_path  # type: ignore[attr-defined]
            # Re-introduce a forbidden shared commands dir.
            _write(root / "assets" / "commands" / "x.md")
            exit_code = vrs.main(["--root", str(root)])
            self.assertEqual(exit_code, 1)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    # Honour $VALIDATE_QUIET for terse output when invoked from a script.
    quiet = os.environ.get("VALIDATE_QUIET") == "1"
    unittest.main(
        module=__name__,
        argv=["__main__"] + ([] if quiet else ["-v"]),
        verbosity=1 if quiet else 2,
        exit=True,
    )
