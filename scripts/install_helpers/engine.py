"""Mechanical install engine for agent-configs.

This module is the shared core behind the three per-tool install
scripts. It performs only copy or link operations from a source tree
(typically ``targets/<tool>/``) into a user-supplied destination
directory. It deliberately refuses to do anything that resembles a
profile manager, rollback system, remote sync tool, or sensitive
config merger.

Design constraints (kept narrow on purpose):

* Safe by default. Dry-run is the default unless the caller asks
  otherwise. No action mutates the filesystem until the plan is
  applied.
* Predictable. Every action is described up front. The CLI prints the
  plan before applying it.
* Boring. Only three outcome kinds: copy, link, or backup-then-copy/
  link. Anything outside the agreed shape becomes a ``SKIP`` or
  ``REFUSE`` action and is reported back to the caller.
* Local. No third-party dependencies. The stdlib is enough.
"""

from __future__ import annotations

import argparse
import enum
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence


# --- Public configuration ----------------------------------------------------

#: Default suffix used when an existing destination file is rotated
#: to a backup. The full backup name is
#: ``<original>.<DEFAULT_BACKUP_SUFFIX>`` with a numeric tail if a
#: previous backup already exists.
DEFAULT_BACKUP_SUFFIX: str = "bak"

#: Path segments (case-insensitive) that name live runtime state we
#: never touch. Any source or destination path containing one of
#: these tokens (as a directory name) is recorded as a ``SKIP`` action
#: with a reason. These are conservative on purpose; missing a real
#: "live state" path is cheaper than copying secret material into a
#: landing area.
SKIP_PATH_TOKENS: frozenset[str] = frozenset(
    {
        "secrets",
        "secret",
        "sessions",
        "session",
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
    }
)

#: Basenames (case-insensitive, with leading dot) that we never copy
#: or link because they are repo-internal or live runtime state. These
#: are applied to every file the engine considers.
SKIP_FILENAMES: frozenset[str] = frozenset(
    {
        ".gitkeep",
        ".gitignore",
        ".ds_store",
        "thumbs.db",
    }
)


class ActionKind(str, enum.Enum):
    """What the engine intends to do for a single file."""

    COPY = "copy"
    LINK = "link"
    BACKUP = "backup"
    SKIP = "skip"
    REFUSE = "refuse"


@dataclass(frozen=True)
class Action:
    """A single planned filesystem action.

    ``reason`` is always populated for ``SKIP`` and ``REFUSE`` actions
    and is empty for actions that the engine would carry out.
    """

    kind: ActionKind
    source: Optional[Path]
    destination: Optional[Path]
    reason: str = ""

    def describe(self) -> str:
        """One-line human description used by the CLI summary."""
        if self.kind is ActionKind.SKIP:
            target = self.source or self.destination
            return f"SKIP   {target}  ({self.reason})"
        if self.kind is ActionKind.REFUSE:
            target = self.destination or self.source
            return f"REFUSE {target}  ({self.reason})"
        if self.kind is ActionKind.BACKUP:
            return f"BAK    {self.destination}  (rotate before overwrite)"
        if self.kind is ActionKind.LINK:
            return f"LINK   {self.source} -> {self.destination}"
        return f"COPY   {self.source} -> {self.destination}"


@dataclass
class InstallPlan:
    """The ordered list of actions the engine intends to take."""

    actions: list[Action] = field(default_factory=list)

    def append(self, action: Action) -> None:
        self.actions.append(action)

    def extend(self, actions: Iterable[Action]) -> None:
        for action in actions:
            self.append(action)

    def filter(self, kind: ActionKind) -> list[Action]:
        return [a for a in self.actions if a.kind is kind]

    def is_empty(self) -> bool:
        return not self.actions

    def count_by_kind(self) -> dict[ActionKind, int]:
        counts: dict[ActionKind, int] = {k: 0 for k in ActionKind}
        for action in self.actions:
            counts[action.kind] += 1
        return counts


@dataclass
class InstallerResult:
    """The outcome of an applied (or dry-run) install.

    The same shape is used in dry-run mode; ``copied``/``linked``/
    ``backed_up`` only count actions that actually mutated the
    filesystem in non-dry-run mode. In dry-run mode they stay at zero
    and the plan is what the caller inspects.
    """

    plan: InstallPlan
    copied: int = 0
    linked: int = 0
    backed_up: int = 0

    def summary_line(self) -> str:
        counts = self.plan.count_by_kind()
        return (
            f"copied={self.copied} linked={self.linked} "
            f"backed_up={self.backed_up} "
            f"skipped={counts[ActionKind.SKIP]} "
            f"refused={counts[ActionKind.REFUSE]}"
        )


# --- Engine ------------------------------------------------------------------


@dataclass
class InstallEngine:
    """Mechanical copy/link installer.

    The engine is configured with a source root (a tool's landing
    area inside this repo, e.g. ``targets/claude-code/``) and a
    destination root (a user-controlled directory, e.g.
    ``~/.claude/``). It walks the source tree, classifies every file
    as ``copy``/``link``/``skip``/``refuse``, builds a plan, and
    applies it.

    The engine never edits files in place. To overwrite a file at the
    destination it first rotates the existing file to a backup. To
    avoid clobbering backups, the numeric tail (``file.bak``,
    ``file.bak.1``, ``file.bak.2`` …) is incremented until a free slot
    is found.

    Live config files (per the per-tool ``live_config`` set) are
    *refused* by default. Callers can pass ``include_live_config=
    True`` to opt in; the engine will still refuse to merge and will
    only stage a copy of the template alongside the live file, never
    overwrite it.
    """

    source_root: Path
    destination_root: Path
    link_mode: bool = False
    include_live_config: bool = False
    backup_suffix: str = DEFAULT_BACKUP_SUFFIX
    live_config: frozenset[str] = field(default_factory=frozenset)

    # --- Plan construction -----------------------------------------------

    def plan(self) -> InstallPlan:
        """Walk the source tree and produce the install plan."""
        if not self.source_root.is_dir():
            plan = InstallPlan()
            plan.append(
                Action(
                    kind=ActionKind.REFUSE,
                    source=self.source_root,
                    destination=None,
                    reason=(
                        f"source root is not a directory: "
                        f"{self.source_root}"
                    ),
                )
            )
            return plan

        out = InstallPlan()
        # Sort for deterministic output: tools and humans can read
        # the plan in a stable order regardless of filesystem
        # ordering.
        for src in sorted(self.source_root.rglob("*")):
            if not src.is_file():
                # Directories are implicit; we create them as needed
                # at apply time. The plan stays file-granular.
                continue
            rel = src.relative_to(self.source_root)
            dst = self.destination_root / rel
            out.extend(self._classify(src, dst, rel))
        return out

    def _classify(self, src: Path, dst: Path, rel: Path) -> list[Action]:
        skip_reason = self._skip_reason(rel)
        if skip_reason is not None:
            return [
                Action(
                    kind=ActionKind.SKIP,
                    source=src,
                    destination=None,
                    reason=skip_reason,
                )
            ]

        is_live = rel.name in self.live_config
        if is_live and not self.include_live_config:
            return [
                Action(
                    kind=ActionKind.REFUSE,
                    source=src,
                    destination=dst,
                    reason=(
                        f"{rel.name} is a live config file; refusing "
                        f"to overwrite. Re-run with "
                        f"--include-live-config to stage the template "
                        f"alongside it (never over the top of it)."
                    ),
                )
            ]

        if is_live and self.include_live_config:
            # Stage the template next to the live file as
            # <name>.template so the user can compare, but never
            # touch the live file itself.
            staged = dst.with_name(dst.name + ".template")
            if self.link_mode:
                return [
                    Action(
                        kind=ActionKind.LINK,
                        source=src,
                        destination=staged,
                    )
                ]
            return [
                Action(
                    kind=ActionKind.COPY,
                    source=src,
                    destination=staged,
                )
            ]

        # Backup before overwrite. Emit a paired BACKUP + COPY/LINK
        # sequence so the engine rotates the existing file aside and
        # then writes the new content into the cleared destination.
        actions: list[Action] = []
        if dst.exists() or dst.is_symlink():
            actions.append(
                Action(
                    kind=ActionKind.BACKUP,
                    source=None,
                    destination=dst,
                )
            )
        if self.link_mode:
            actions.append(
                Action(
                    kind=ActionKind.LINK, source=src, destination=dst
                )
            )
        else:
            actions.append(
                Action(
                    kind=ActionKind.COPY, source=src, destination=dst
                )
            )
        return actions

    @staticmethod
    def _skip_reason(rel: Path) -> Optional[str]:
        """Return a human reason if ``rel`` should be skipped.

        Returns ``None`` if the path is safe to install.
        """
        name_lower = rel.name.lower()
        if name_lower in SKIP_FILENAMES:
            return f"repo-internal file ({rel.name})"

        for part in rel.parts:
            part_lower = part.lower()
            if part_lower in SKIP_PATH_TOKENS:
                return f"live runtime state path ({part})"
            if (
                part_lower.startswith(".")
                and part_lower not in SKIP_FILENAMES
                and part_lower not in {".", ".."}
            ):
                # Dotfile/dotdir safety net. The leading-dot check
                # catches `.env`, `.ssh`, `.aws`, etc.
                return f"dotfile/dotdir under source ({part})"
        return None

    # --- Apply -----------------------------------------------------------

    def apply(self, plan: InstallPlan) -> InstallerResult:
        """Apply the plan. Mutates the filesystem only when needed."""
        result = InstallerResult(plan=plan)
        # Walk actions in plan order so any backup created in front
        # of a copy is visible to the user as a separate line.
        for action in plan.actions:
            if action.kind is ActionKind.SKIP:
                continue
            if action.kind is ActionKind.REFUSE:
                continue
            if action.kind is ActionKind.BACKUP:
                assert action.destination is not None
                self._rotate_backup(action.destination)
                result.backed_up += 1
                continue

            assert action.source is not None
            assert action.destination is not None
            action.destination.parent.mkdir(parents=True, exist_ok=True)
            if action.kind is ActionKind.LINK:
                self._link(action.source, action.destination)
                result.linked += 1
            elif action.kind is ActionKind.COPY:
                self._copy(action.source, action.destination)
                result.copied += 1
        return result

    def _rotate_backup(self, target: Path) -> Path:
        """Move ``target`` aside to the next free backup slot.

        Returns the path of the backup that was created.
        """
        suffix = self.backup_suffix
        candidate = target.with_name(target.name + f".{suffix}")
        n = 1
        while candidate.exists() or candidate.is_symlink():
            candidate = target.with_name(f"{target.name}.{suffix}.{n}")
            n += 1
        target.rename(candidate)
        return candidate

    @staticmethod
    def _copy(src: Path, dst: Path) -> None:
        # We deliberately use shutil.copyfile + a metadata-preserving
        # followup so a dry-run-then-real-run can rely on the file
        # ending up identical to the source.
        shutil.copyfile(src, dst)
        shutil.copymode(src, dst, follow_symlinks=True)

    @staticmethod
    def _link(src: Path, dst: Path) -> None:
        # Use a symlink rather than a hardlink so a destination that
        # lives on a different filesystem still works, and so the
        # relationship is explicit (``ls -l`` shows the source).
        if dst.exists() or dst.is_symlink():
            # Should be unreachable: BACKUP clears the path before
            # we get here. Guard anyway to keep the contract tight.
            raise FileExistsError(
                f"refusing to clobber existing destination: {dst}"
            )
        os.symlink(src, dst)


# --- CLI rendering helpers ---------------------------------------------------


def render_plan(plan: InstallPlan, stream=sys.stdout) -> None:
    """Print the plan to ``stream`` in a stable, readable format."""
    for action in plan.actions:
        print(action.describe(), file=stream)


def warn_skips_and_refusals(plan: InstallPlan, stream=sys.stderr) -> None:
    """Emit a short note about skip/refuse counts."""
    counts = plan.count_by_kind()
    if counts[ActionKind.SKIP] or counts[ActionKind.REFUSE]:
        print(
            f"note: {counts[ActionKind.SKIP]} skipped, "
            f"{counts[ActionKind.REFUSE]} refused "
            f"(see plan above for reasons)",
            file=stream,
        )


# --- Per-tool CLI driver -----------------------------------------------------


def build_parser(
    tool_name: str,
    default_dest: str,
    live_config_files: Sequence[str],
    source_subdir: str,
    description: str,
) -> argparse.ArgumentParser:
    """Build the standard argparse parser for a per-tool CLI."""
    parser = argparse.ArgumentParser(
        prog=f"install_{tool_name}",
        description=description,
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent,
        help=(
            "Path to the agent-configs repository root "
            "(default: parent of scripts/)"
        ),
    )
    # ``Path(default_dest)`` does not expand ``~``; resolve it now so
    # the default value and the help text describe a real absolute
    # path, and the runtime can never treat a literal ``~`` segment
    # as a relative directory under the current working directory.
    default_dest_resolved = Path(default_dest).expanduser()
    parser.add_argument(
        "--dest",
        type=Path,
        default=default_dest_resolved,
        help=(
            f"Destination directory for {tool_name} "
            f"(default: {default_dest_resolved})"
        ),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--copy",
        dest="link_mode",
        action="store_false",
        help="Copy files into the destination (default).",
    )
    mode.add_argument(
        "--link",
        dest="link_mode",
        action="store_true",
        help=(
            "Symlink each file into the destination instead of "
            "copying. Edits to the source will be visible to the "
            "target tool."
        ),
    )
    parser.set_defaults(link_mode=False)
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help=(
            "Report the planned actions and exit without modifying "
            "the destination. This is the safe default; pass "
            "--apply to actually mutate the destination."
        ),
    )
    parser.add_argument(
        "--apply",
        dest="dry_run",
        action="store_false",
        help="Apply the plan. Required for any filesystem mutation.",
    )
    parser.set_defaults(dry_run=True)
    parser.add_argument(
        "--include-live-config",
        action="store_true",
        help=(
            "Stage live config templates alongside an existing live "
            "config file. The engine NEVER overwrites a live config; "
            "it copies the template next to it as <name>.template so "
            "the user can compare. Off by default."
        ),
    )
    parser.add_argument(
        "--backup-suffix",
        default=DEFAULT_BACKUP_SUFFIX,
        help=(
            "Suffix for rotated backups of overwritten files "
            f"(default: {DEFAULT_BACKUP_SUFFIX})."
        ),
    )
    parser.add_argument(
        "--list-live-config",
        action="store_true",
        help=(
            "Print the live config filenames this tool protects "
            "and exit."
        ),
    )
    parser.set_defaults(
        _tool_name=tool_name,
        _source_subdir=source_subdir,
        _live_config=tuple(live_config_files),
    )
    return parser


def run_cli(
    parser: argparse.ArgumentParser,
    argv: Optional[Sequence[str]] = None,
) -> int:
    """Drive a per-tool CLI end-to-end.

    Returns a Unix-style exit code: 0 on success, 1 on validation
    failure, 2 on usage error.
    """
    args = parser.parse_args(argv)

    tool_name: str = args._tool_name  # type: ignore[attr-defined]
    source_subdir: str = args._source_subdir  # type: ignore[attr-defined]
    live_config: tuple[str, ...] = args._live_config  # type: ignore[attr-defined]

    if args.list_live_config:
        print(f"{tool_name}: protected live config files:")
        for name in live_config:
            print(f"  - {name}")
        return 0

    # ``argparse(type=Path)`` does not expand a leading ``~`` for
    # either user-supplied ``--dest`` values or the default. Resolve
    # it here so every code path below (engine construction, the
    # dry-run/apply banner, the rendered plan) sees the same
    # HOME-relative destination and never a literal ``~/.x`` segment
    # that would resolve under cwd.
    destination_root = args.dest.expanduser()
    source_root = args.repo / source_subdir
    engine = InstallEngine(
        source_root=source_root,
        destination_root=destination_root,
        link_mode=args.link_mode,
        include_live_config=args.include_live_config,
        backup_suffix=args.backup_suffix,
        live_config=frozenset(live_config),
    )

    plan = engine.plan()
    counts = plan.count_by_kind()

    # Refusal before the plan: source root missing is surfaced as a
    # single REFUSE action. Don't even print a plan; bail with code 1.
    if counts[ActionKind.REFUSE] and not engine.source_root.is_dir():
        render_plan(plan, stream=sys.stderr)
        return 1

    if args.dry_run:
        print(
            f"[dry-run] {tool_name}: planned actions for "
            f"{source_root} -> {destination_root}"
        )
        render_plan(plan)
        warn_skips_and_refusals(plan)
        return 0

    print(
        f"[apply] {tool_name}: applying {source_root} -> {destination_root}"
    )
    render_plan(plan)
    warn_skips_and_refusals(plan)
    result = engine.apply(plan)
    print(f"[apply] done. {result.summary_line()}")
    return 0


__all__ = [
    "Action",
    "ActionKind",
    "DEFAULT_BACKUP_SUFFIX",
    "InstallEngine",
    "InstallerResult",
    "InstallPlan",
    "SKIP_FILENAMES",
    "SKIP_PATH_TOKENS",
    "build_parser",
    "render_plan",
    "run_cli",
    "warn_skips_and_refusals",
]
