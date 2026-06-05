#!/usr/bin/env python3
"""Tests for the install_helpers package and the three CLI scripts.

The tests build small, in-memory source trees that mirror the shape of
the real ``targets/<tool>/`` landing areas, then drive the engine
and the per-tool CLIs through the behaviours the issue requires.

Behaviour coverage:

  * Dry-run reports the plan and does not mutate the destination.
  * Copy mode copies files; link mode symlinks them.
  * Overwritten files are rotated to a backup before being replaced.
  * Paths whose name or any segment matches a skip token are recorded
    as ``SKIP`` actions.
  * Live config files are refused by default; staged as a template
    alongside the live file only with ``--include-live-config``.
  * Each per-tool CLI lists its protected live config filenames.

Run with:

    python3 scripts/test_install_helpers.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import install_helpers  # noqa: E402
from install_helpers import engine  # noqa: E402
from install_helpers.engine import (  # noqa: E402
    ActionKind,
    InstallEngine,
    InstallPlan,
    InstallerResult,
    SKIP_PATH_TOKENS,
    build_parser,
    run_cli,
)


@dataclass(frozen=True)
class _ToolCase:
    script_name: str
    source_subdir: str
    live_configs: tuple[str, ...]
    template_basename: str


CLAUDE_CASE = _ToolCase(
    script_name="install_claude_code.py",
    source_subdir="targets/claude-code",
    live_configs=("settings.json", "mcp.json"),
    template_basename="settings.json.template",
)
CODEX_CASE = _ToolCase(
    script_name="install_codex.py",
    source_subdir="targets/codex",
    live_configs=("config.toml",),
    template_basename="config.toml.template",
)
OMP_CASE = _ToolCase(
    script_name="install_omp.py",
    source_subdir="targets/oh-my-pi",
    live_configs=("omp.config.json",),
    template_basename="omp.config.json.template",
)


def _seed_source(
    root: Path,
    template_basename: str = "settings.json.template",
    extras: Iterable[tuple[str, str]] = (),
) -> None:
    """Build a minimal but realistic source tree at ``root``.

    Mirrors the shape of a real ``targets/<tool>/`` landing area:
    a README, a template config, agents/commands/hooks/skills stubs
    that contain content, and any extra paths the caller wants to
    add.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# tool readme\n")
    (root / template_basename).write_text("# template content\n")
    (root / "agents").mkdir()
    (root / "agents" / "explore.md").write_text("# explore\n")
    (root / "agents" / ".gitkeep").write_text("")
    (root / "commands").mkdir()
    (root / "commands" / "review.md").write_text("# review\n")
    (root / "commands" / ".gitkeep").write_text("")
    (root / "hooks").mkdir()
    (root / "hooks" / "pre_tool_use.py").write_text("# hook\n")
    (root / "hooks" / ".gitkeep").write_text("")
    (root / "skills").mkdir()
    (root / "skills" / "example.md").write_text("# skill\n")
    (root / "skills" / ".gitkeep").write_text("")
    for rel, content in extras:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


# --- Engine unit tests ------------------------------------------------------


class EnginePlanTest(unittest.TestCase):
    """The engine classifies every source file into a sequence of actions."""

    def test_empty_source_root_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "missing"
            dst = Path(tmp) / "dest"
            plan = InstallEngine(
                source_root=src,
                destination_root=dst,
            ).plan()
            kinds = [a.kind for a in plan.actions]
            self.assertEqual(kinds, [ActionKind.REFUSE])

    def test_baseline_source_produces_copy_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            dst = root / "dest"
            _seed_source(src)
            plan = InstallEngine(
                source_root=src, destination_root=dst
            ).plan()
            copies = plan.filter(ActionKind.COPY)
            # README, template, agents/explore, commands/review,
            # hooks/pre_tool_use, skills/example.  No backups because
            # the destination is empty.
            self.assertGreaterEqual(len(copies), 6)
            for action in copies:
                self.assertIsNotNone(action.source)
                self.assertIsNotNone(action.destination)


class EngineApplyTest(unittest.TestCase):
    """apply() mutates the filesystem in copy and link modes."""

    def test_copy_mode_creates_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            dst = root / "dest"
            _seed_source(src)
            engine_obj = InstallEngine(
                source_root=src, destination_root=dst
            )
            plan = engine_obj.plan()
            result = engine_obj.apply(plan)
            self.assertGreater(result.copied, 0)
            self.assertEqual(result.linked, 0)
            self.assertEqual(result.backed_up, 0)
            self.assertTrue((dst / "README.md").is_file())
            self.assertTrue((dst / "settings.json.template").is_file())

    def test_link_mode_creates_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            dst = root / "dest"
            _seed_source(src)
            engine_obj = InstallEngine(
                source_root=src,
                destination_root=dst,
                link_mode=True,
            )
            plan = engine_obj.plan()
            result = engine_obj.apply(plan)
            self.assertGreater(result.linked, 0)
            self.assertEqual(result.copied, 0)
            # Symlinks resolve to source content.
            target = dst / "README.md"
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.read_text(), "# tool readme\n")


class EngineBackupTest(unittest.TestCase):
    """Existing files are rotated to a backup before overwrite."""

    def test_existing_destination_is_rotated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            dst = root / "dest"
            _seed_source(src)
            # Pre-populate the destination with a file the engine
            # will want to overwrite.
            (dst / "README.md").parent.mkdir(parents=True, exist_ok=True)
            (dst / "README.md").write_text("# OLD CONTENT\n")
            engine_obj = InstallEngine(
                source_root=src, destination_root=dst
            )
            plan = engine_obj.plan()
            # The plan should now contain a paired BACKUP + COPY for
            # the README so the engine can both rotate and replace.
            kinds = [a.kind for a in plan.actions]
            self.assertIn(ActionKind.BACKUP, kinds)
            self.assertIn(ActionKind.COPY, kinds)
            result = engine_obj.apply(plan)
            self.assertGreater(result.backed_up, 0)
            self.assertTrue((dst / "README.md.bak").exists())
            self.assertEqual(
                (dst / "README.md.bak").read_text(), "# OLD CONTENT\n"
            )
            # New content is in place.
            self.assertEqual(
                (dst / "README.md").read_text(), "# tool readme\n"
            )

    def test_existing_backup_is_numbered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            dst = root / "dest"
            _seed_source(src)
            (dst / "README.md").parent.mkdir(parents=True, exist_ok=True)
            (dst / "README.md").write_text("# OLD1\n")
            (dst / "README.md.bak").write_text("# OLD0\n")
            engine_obj = InstallEngine(
                source_root=src, destination_root=dst
            )
            plan = engine_obj.plan()
            result = engine_obj.apply(plan)
            # First rotation lands at .bak.1 because .bak is taken.
            self.assertTrue((dst / "README.md.bak.1").exists())
            self.assertEqual(
                (dst / "README.md.bak.1").read_text(), "# OLD1\n"
            )

    def test_existing_symlink_is_rotated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            dst = root / "dest"
            _seed_source(src)
            (dst / "README.md").parent.mkdir(parents=True, exist_ok=True)
            (dst / "README.md").symlink_to("/some/where/else")
            engine_obj = InstallEngine(
                source_root=src, destination_root=dst
            )
            plan = engine_obj.plan()
            result = engine_obj.apply(plan)
            self.assertGreater(result.backed_up, 0)
            self.assertTrue((dst / "README.md.bak").is_symlink())
            self.assertEqual(
                (dst / "README.md").read_text(), "# tool readme\n"
            )


class EngineSkipTest(unittest.TestCase):
    """Skip tokens and filenames remove files from the plan."""

    def test_skip_token_in_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            dst = root / "dest"
            # Path containing a "secrets" segment is skipped.
            (src / "secrets").mkdir(parents=True)
            (src / "secrets" / "api.txt").write_text("TOPSECRET")
            (src / "cache").mkdir(parents=True)
            (src / "cache" / "index.db").write_text("BIN")
            (src / "README.md").write_text("# readme\n")
            plan = InstallEngine(
                source_root=src, destination_root=dst
            ).plan()
            skipped_sources = {
                a.source for a in plan.filter(ActionKind.SKIP)
            }
            self.assertIn(src / "secrets" / "api.txt", skipped_sources)
            self.assertIn(src / "cache" / "index.db", skipped_sources)
            # README is still copied.
            copies = plan.filter(ActionKind.COPY)
            self.assertTrue(
                any(a.source == src / "README.md" for a in copies)
            )

    def test_skip_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            dst = root / "dest"
            (src / "agents").mkdir(parents=True)
            (src / "agents" / ".gitkeep").write_text("")
            (src / "agents" / "real.md").write_text("# real\n")
            plan = InstallEngine(
                source_root=src, destination_root=dst
            ).plan()
            skipped = {a.source for a in plan.filter(ActionKind.SKIP)}
            self.assertIn(src / "agents" / ".gitkeep", skipped)
            copies = {a.source for a in plan.filter(ActionKind.COPY)}
            self.assertIn(src / "agents" / "real.md", copies)

    def test_dotdir_under_source_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            dst = root / "dest"
            (src / ".ssh").mkdir(parents=True)
            (src / ".ssh" / "id_rsa").write_text("PRIVATE")
            (src / "README.md").write_text("# r\n")
            plan = InstallEngine(
                source_root=src, destination_root=dst
            ).plan()
            skipped = {a.source for a in plan.filter(ActionKind.SKIP)}
            self.assertIn(src / ".ssh" / "id_rsa", skipped)


class EngineLiveConfigTest(unittest.TestCase):
    """Live config files are refused unless explicitly opted in."""

    def test_live_config_refused_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            dst = root / "dest"
            # Source tree contains a file whose name matches a live
            # config token. The engine must refuse rather than copy.
            src.mkdir()
            (src / "settings.json").write_text('{"model":"X"}')
            (src / "README.md").write_text("# r\n")
            plan = InstallEngine(
                source_root=src,
                destination_root=dst,
                live_config=frozenset({"settings.json"}),
            ).plan()
            refused = plan.filter(ActionKind.REFUSE)
            self.assertTrue(
                any(a.source == src / "settings.json" for a in refused)
            )

    def test_live_config_staged_as_template_with_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            dst = root / "dest"
            src.mkdir()
            (src / "settings.json").write_text('{"model":"X"}')
            plan = InstallEngine(
                source_root=src,
                destination_root=dst,
                include_live_config=True,
                live_config=frozenset({"settings.json"}),
            ).plan()
            # The action must be a COPY/LINK with destination
            # settings.json.template, not settings.json.
            live_actions = [
                a
                for a in plan.actions
                if a.source == src / "settings.json"
            ]
            self.assertEqual(len(live_actions), 1)
            action = live_actions[0]
            self.assertIn(
                action.kind, {ActionKind.COPY, ActionKind.LINK}
            )
            self.assertEqual(
                action.destination, dst / "settings.json.template"
            )


class DryRunNoMutationTest(unittest.TestCase):
    """Calling plan() never writes to the destination."""

    def test_plan_does_not_create_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            dst = root / "dest"
            _seed_source(src)
            InstallEngine(
                source_root=src, destination_root=dst
            ).plan()
            self.assertFalse(dst.exists())


# --- Per-tool CLI tests ------------------------------------------------------


# Subclass of unittest.TestCase that should not be discovered as a
# test class. We use a name that unittest discovery would still pick
# up; the guard is a metaclass check via a sentinel method.
class _PerToolCliBase(unittest.TestCase):
    """Common assertions for the three CLI entry points.

    Setting ``__test__ = False`` tells the unittest discovery
    machinery to ignore this base class even though it defines
    ``test_*`` methods; the concrete subclasses inherit and run
    them.
    """

    __test__ = False

    # Concrete subclasses MUST set ``tool_case`` to a populated
    # ``_ToolCase``. Setting it on the base class raises at
    # construction time, so the abstract base is never discoverable.
    tool_case: _ToolCase = None  # type: ignore[assignment]

    def setUp(self) -> None:  # noqa: D401 - unittest convention
        if self.tool_case is None:
            self.skipTest("abstract base class")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        # Build a synthetic source tree that mirrors the real
        # targets/<tool>/ shape. The CLI's --repo points at a
        # parent directory containing the synthetic source.
        self.repo = self.tmp_path / "repo"
        src = self.repo / self.tool_case.source_subdir
        _seed_source(src, template_basename=self.tool_case.template_basename)
        self.dest = self.tmp_path / "dest"

    def _run(
        self, *extra: str, dest: Path | None = None
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / self.tool_case.script_name),
                "--repo",
                str(self.repo),
                "--dest",
                str(dest or self.dest),
                *extra,
            ],
            capture_output=True,
            text=True,
        )

    def test_dry_run_default_does_not_mutate(self) -> None:
        result = self._run()  # no --apply, so dry-run
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[dry-run]", result.stdout)
        self.assertFalse(self.dest.exists())

    def test_apply_copies_files(self) -> None:
        result = self._run("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.dest / "README.md").is_file())
        self.assertTrue(
            (self.dest / self.tool_case.template_basename).is_file()
        )

    def test_apply_link_creates_symlinks(self) -> None:
        result = self._run("--apply", "--link")
        self.assertEqual(result.returncode, 0, result.stderr)
        target = self.dest / "README.md"
        self.assertTrue(target.is_symlink())

    def test_apply_refuses_live_config_by_default(self) -> None:
        # Plant a live config file in the destination before
        # applying. The source has only the template; the live
        # config file in dest must be preserved untouched and the
        # template must be staged alongside it.
        live_name = self.tool_case.live_configs[0]
        self.dest.mkdir(parents=True, exist_ok=True)
        (self.dest / live_name).write_text('{"model":"USER"}')
        result = self._run("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        # Live config is untouched; template is staged beside it.
        self.assertEqual(
            (self.dest / live_name).read_text(), '{"model":"USER"}'
        )
        # The matching template should be staged.
        self.assertTrue(
            (self.dest / self.tool_case.template_basename).exists()
        )

    def test_list_live_config_prints_names(self) -> None:
        result = self._run("--list-live-config")
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in self.tool_case.live_configs:
            self.assertIn(name, result.stdout)

    def test_apply_with_existing_destination_rotates_backup(self) -> None:
        self.dest.mkdir(parents=True, exist_ok=True)
        (self.dest / "README.md").write_text("# OLD\n")
        result = self._run("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.dest / "README.md.bak").exists())
        self.assertEqual(
            (self.dest / "README.md.bak").read_text(), "# OLD\n"
        )
        self.assertEqual(
            (self.dest / "README.md").read_text(), "# tool readme\n"
        )


class ClaudeCodeCliTest(_PerToolCliBase):
    tool_case = CLAUDE_CASE


class CodexCliTest(_PerToolCliBase):
    tool_case = CODEX_CASE


class OmpCliTest(_PerToolCliBase):
    tool_case = OMP_CASE


# --- Default dest expansion (issue #6 review blocker) ---------------------


class DefaultDestExpansionTest(unittest.TestCase):
    """``~/.x`` default destinations must expand, not be literal ``~``.

    Issue #6 review blocker: ``argparse(type=Path)`` does not expand a
    leading ``~`` for either the user-supplied ``--dest`` value or the
    default produced from ``Path(default_dest)``. Before the fix a
    default install from an arbitrary cwd could create ``./~/.claude``
    (literal ``~`` segment resolved against cwd) instead of
    ``$HOME/.claude``.

    These tests invoke the real per-tool CLIs through ``subprocess``
    with no ``--dest`` argument, a temporary cwd, and ``HOME`` pointed
    at a temporary directory. The expected destination is
    ``$HOME/.claude``, ``$HOME/.codex``, and ``$HOME/.omp``
    respectively — never ``cwd/~``.
    """

    __test__ = True

    # Each subclass sets ``tool_case`` to a ``_ToolCase``. We don't
    # reuse ``_PerToolCliBase`` here because the launcher must NOT
    # pass ``--dest`` (that is exactly what we are not testing) and
    # must redirect ``HOME`` and ``cwd``.
    tool_case: "_ToolCase | None" = None

    def setUp(self) -> None:  # noqa: D401 - unittest convention
        if self.tool_case is None:
            self.skipTest("abstract base class")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = Path(self.tmp.name)
        # HOME points at the temp root so ``~/.x`` resolves there.
        self.home = self.tmp_path / "home"
        self.home.mkdir()
        # cwd is a *different* temp directory; if the engine ever
        # resolves ``~`` relative to cwd the test catches it.
        self.cwd = self.tmp_path / "cwd"
        self.cwd.mkdir()
        # Synthetic source tree inside the temp root so we can
        # invoke the CLI without touching the real repo.
        self.repo = self.tmp_path / "repo"
        src = self.repo / self.tool_case.source_subdir
        _seed_source(src, template_basename=self.tool_case.template_basename)

    def _expected_dest(self) -> Path:
        # Mirror the DEFAULT_DEST in each install_*.py module.
        return self.home / {
            CLAUDE_CASE: ".claude",
            CODEX_CASE: ".codex",
            OMP_CASE: ".omp",
        }[self.tool_case]

    def _launch(self, *extra: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / self.tool_case.script_name),
                "--repo",
                str(self.repo),
                *extra,
            ],
            capture_output=True,
            text=True,
            cwd=str(self.cwd),
            env=env,
        )

    def _assert_no_cwd_tilde(
        self, result: subprocess.CompletedProcess
    ) -> None:
        """The CLI must not plan/apply anywhere under cwd/."""
        # 1. Plan/banner text must reference the HOME-expanded
        #    destination, not a literal ``~``.
        self.assertNotIn("~/", result.stdout)
        self.assertNotIn("/~/", result.stdout)
        # 2. Nothing was created in the cwd that we ran from.
        cwd_children = list(self.cwd.iterdir())
        self.assertEqual(
            cwd_children,
            [],
            f"CLI wrote under cwd: {cwd_children}",
        )
        # 3. The HOME-expanded destination directory itself was
        #    touched (plan-only would NOT create the directory, but
        #    the path text in the plan must match). See per-test
        #    asserts for the create-or-not expectation.
        self.assertNotIn(str(self.cwd), result.stdout)

    def test_dry_run_uses_home_expanded_dest(self) -> None:
        expected = self._expected_dest()
        result = self._launch()  # default mode is dry-run
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[dry-run]", result.stdout)
        # Banner names the HOME-expanded destination.
        self.assertIn(str(expected), result.stdout)
        # No literal ``~`` anywhere in the plan output.
        self.assertNotIn("~/", result.stdout)
        # And nothing was written under the cwd we launched from.
        self._assert_no_cwd_tilde(result)
        # The HOME/.x directory must not yet exist (dry-run is the
        # safe default and the plan only mutates on --apply).
        self.assertFalse(expected.exists())

    def test_apply_uses_home_expanded_dest(self) -> None:
        expected = self._expected_dest()
        result = self._launch("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[apply]", result.stdout)
        # Banner names the HOME-expanded destination.
        self.assertIn(str(expected), result.stdout)
        # No literal ``~`` anywhere in the output.
        self.assertNotIn("~/", result.stdout)
        # Nothing was created in the launch cwd.
        self._assert_no_cwd_tilde(result)
        # Files actually landed under HOME/.x.
        self.assertTrue(expected.is_dir())
        self.assertTrue((expected / "README.md").is_file())
        self.assertTrue(
            (expected / self.tool_case.template_basename).is_file()
        )

    def test_apply_link_uses_home_expanded_dest(self) -> None:
        expected = self._expected_dest()
        result = self._launch("--apply", "--link")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(expected), result.stdout)
        self.assertNotIn("~/", result.stdout)
        self._assert_no_cwd_tilde(result)
        self.assertTrue((expected / "README.md").is_symlink())


class ClaudeCodeDefaultDestExpansionTest(DefaultDestExpansionTest):
    tool_case = CLAUDE_CASE


class CodexDefaultDestExpansionTest(DefaultDestExpansionTest):
    tool_case = CODEX_CASE


class OmpDefaultDestExpansionTest(DefaultDestExpansionTest):
    tool_case = OMP_CASE


# --- Real oh-my-pi landing area (issue #11) --------------------------------
#
# The oh-my-pi target landing area is the only one of the three that carries
# a real, populated `extensions/<name>/` subtree migrated from a local
# runtime. The install helper's behaviour for that subtree is part of the
# contract: every file the migration intentionally brought across must land
# as a COPY action in the plan, the `.gitkeep` placeholders are the only
# SKIP actions, and the dry-run CLI must surface the same set of files
# without mutating the destination.

OMP_REAL_LANDING_EXPECTED_COPIES: tuple[str, ...] = (
    "README.md",
    "omp.config.json.template",
    "extensions/codebase-memory-gate/index.ts",
    "extensions/codebase-memory-gate/classification-helpers.ts",
    "extensions/codebase-memory-gate/tests/run-tests.sh",
    "extensions/codebase-memory-gate/tests/gate-classification.test.mjs",
    "extensions/codebase-memory-gate/tests/behavior-smoke.test.mjs",
    "extensions/codebase-memory-gate/tests/e2e-smoke.test.mjs",
    "extensions/codebase-memory-gate/tests/proxy-epipe.test.mjs",
)

# Paths whose `.gitkeep` placeholders are still in the tree. The engine
# classifies these as SKIP (repo-internal file); they are not regression
# signals, but any other SKIP/REFUSE action is.
OMP_REAL_LANDING_ALLOWED_SKIPS: frozenset[str] = frozenset(
    {
        "extensions/.gitkeep",
        "skills/.gitkeep",
    }
)


class OmpRealLandingAreaTest(unittest.TestCase):
    """Lock the install-helper plan for the real ``targets/oh-my-pi/``
    landing area after the issue #11 migration.

    The plan is checked twice: once by driving the engine in-process, and
    once by invoking the real ``install_omp.py`` CLI in dry-run mode. Both
    must agree on the file set so a future refactor that drops or skips a
    migrated file fails the test rather than silently regressing the
    installer contract.
    """

    __test__ = True

    def setUp(self) -> None:  # noqa: D401 - unittest convention
        self.real_landing = REPO_ROOT / "targets" / "oh-my-pi"
        if not self.real_landing.is_dir():
            self.skipTest(
                f"real oh-my-pi landing area missing: {self.real_landing}"
            )

    def _expected_relpaths(self) -> set[str]:
        return set(OMP_REAL_LANDING_EXPECTED_COPIES)

    def test_engine_plan_matches_expected_copies(self) -> None:
        """The engine must plan a COPY for every migrated file and a SKIP
        only for the two ``.gitkeep`` placeholders. Anything else is a
        regression: either a file was added to the migration without
        updating the test, or the engine misclassified a known file.
        """
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "dest"
            plan = InstallEngine(
                source_root=self.real_landing,
                destination_root=dst,
            ).plan()

        copy_relpaths = {
            a.source.relative_to(self.real_landing).as_posix()
            for a in plan.filter(ActionKind.COPY)
        }
        skip_relpaths = {
            a.source.relative_to(self.real_landing).as_posix()
            for a in plan.filter(ActionKind.SKIP)
        }
        refused = plan.filter(ActionKind.REFUSE)
        backups = plan.filter(ActionKind.BACKUP)

        self.assertEqual(
            copy_relpaths,
            self._expected_relpaths(),
            f"COPY set drifted. unexpected={copy_relpaths ^ self._expected_relpaths()}",
        )
        self.assertEqual(
            skip_relpaths,
            OMP_REAL_LANDING_ALLOWED_SKIPS,
            f"unexpected SKIP entries: {skip_relpaths - OMP_REAL_LANDING_ALLOWED_SKIPS}",
        )
        self.assertEqual(
            refused,
            [],
            f"no migrated file should be REFUSE; got: {[(a.source, a.reason) for a in refused]}",
        )
        # Destination is empty so no BACKUP actions are expected.
        self.assertEqual(
            backups,
            [],
            "no BACKUP actions expected on a fresh destination",
        )

    def test_dry_run_cli_lists_migrated_files(self) -> None:
        """``install_omp.py`` dry-run must print a COPY line for every
        migrated file. The CLI is the user-facing contract; the engine
        test above guards the library API, this test guards the CLI.
        """
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "dest"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / OMP_CASE.script_name),
                    "--repo",
                    str(REPO_ROOT),
                    "--dest",
                    str(dest),
                ],
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[dry-run]", result.stdout)
        for relpath in OMP_REAL_LANDING_EXPECTED_COPIES:
            marker_line = f"COPY   {self.real_landing}/{relpath} -> "
            self.assertIn(
                marker_line,
                result.stdout,
                f"dry-run plan missing COPY for {relpath}\n--- stdout ---\n{result.stdout}",
            )
        # Only the two .gitkeep files are allowed to appear as SKIP.
        for line in result.stdout.splitlines():
            if line.startswith("SKIP"):
                self.assertIn(
                    ".gitkeep",
                    line,
                    f"unexpected non-.gitkeep SKIP: {line}",
                )

    def test_dry_run_does_not_mutate_destination(self) -> None:
        """Issue #11 acceptance: dry-run must not modify the destination.
        The default destination is ``~/.omp``; on a CI runner that is
        outside the temp dir, so a stray write there would be a real
        regression. The engine test above covers the engine's no-mutation
        contract; this test pins the CLI's no-mutation contract for the
        real landing area.
        """
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "dest"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / OMP_CASE.script_name),
                    "--repo",
                    str(REPO_ROOT),
                    "--dest",
                    str(dest),
                ],
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(
            dest.exists(),
            f"dry-run must not create {dest}; found entries: "
            f"{list(dest.iterdir()) if dest.exists() else 'n/a'}",
        )


# --- Public API surface ------------------------------------------------------


class PublicApiTest(unittest.TestCase):
    """The package's ``__all__`` is the contract for library callers."""

    def test_installer_helpers_exports_match_init(self) -> None:
        for name in (
            "Action",
            "ActionKind",
            "InstallEngine",
            "InstallerResult",
            "InstallPlan",
            "DEFAULT_BACKUP_SUFFIX",
            "SKIP_PATH_TOKENS",
            "SKIP_FILENAMES",
        ):
            self.assertTrue(
                hasattr(install_helpers, name),
                f"install_helpers.{name} missing",
            )
            self.assertIn(name, install_helpers.__all__)

    def test_skip_token_set_is_nonempty(self) -> None:
        self.assertIn("secrets", SKIP_PATH_TOKENS)
        self.assertIn("cache", SKIP_PATH_TOKENS)
        self.assertIn("history", SKIP_PATH_TOKENS)


if __name__ == "__main__":
    quiet = os.environ.get("INSTALL_HELPERS_QUIET") == "1"
    unittest.main(
        module=__name__,
        argv=["__main__"] + ([] if quiet else ["-v"]),
        verbosity=1 if quiet else 2,
        exit=True,
    )
