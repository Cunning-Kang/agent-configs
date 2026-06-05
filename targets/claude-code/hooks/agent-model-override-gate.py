#!/usr/bin/env python3
"""Block unapproved Agent model overrides in Claude Code hooks."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sys
import time
from pathlib import Path

MARKER_PATTERN = re.compile(r"\[MODEL_OVERRIDE_APPROVED:([^\]]+)\]")
MARKER_FIELD_PATTERN = re.compile(r"([A-Za-z0-9_-]+)=([^;=]+)(?:;|$)")
AGENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._:/-]+$")
SAFE_MODEL_CHARS = re.compile(r"^[A-Za-z0-9._-]+$")
EXPIRES_PATTERN = re.compile(r"^[0-9]+$")
SIG_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
MODEL_LINE_PATTERN = re.compile(r"\s*model\s*:\s*[\"']?([^\"'\s#]+)")
DEFAULT_SECRET_PATH = Path.home() / ".claude" / "agent-model-override-secret"
MAX_CLOCK_SKEW_SECONDS = 300

INHERIT_MODEL = "__inherit__"

BUILTIN_AGENT_DEFAULT_MODELS = {
    # Claude Code built-in agents do not have .claude/agents/*.md frontmatter.
    "Explore": "haiku",
    "Plan": INHERIT_MODEL,
    "claude": INHERIT_MODEL,
    "claude/general-purpose/Plan": INHERIT_MODEL,
    "claude-code-guide": "haiku",
    "general-purpose": INHERIT_MODEL,
    "statusline-setup": "sonnet",
    "agent-skills:code-reviewer": INHERIT_MODEL,
    "agent-skills:security-auditor": INHERIT_MODEL,
    "agent-skills:test-engineer": INHERIT_MODEL,
}



def emit_block(reason: str) -> None:
    print(json.dumps({
        "continue": False,
        "stopReason": reason,
        "decision": "block",
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }))


def parse_marker_fields(prompt: str) -> dict[str, str] | None:
    """Parse marker fields, rejecting values containing ; or = to prevent format ambiguity."""
    marker_match = MARKER_PATTERN.search(prompt)
    if not marker_match:
        return None

    marker_body = marker_match.group(1).strip()
    matches = MARKER_FIELD_PATTERN.findall(marker_body)
    if not matches:
        return None
    if len(matches) != marker_body.count(";") + 1:
        return None
    if marker_body.count("=") != len(matches):
        return None
    return dict(matches)


def validate_marker_fields(fields: dict[str, str]) -> bool:
    """Validate marker field values to prevent ;/= format ambiguity."""
    expected_default = fields.get("expected-default", "")
    override = fields.get("override", "")
    expires = fields.get("expires", "")
    sig = fields.get("sig", "")

    if not (SAFE_MODEL_CHARS.match(expected_default) and SAFE_MODEL_CHARS.match(override)):
        return False
    if not EXPIRES_PATTERN.match(expires):
        return False
    if not SIG_PATTERN.match(sig):
        return False
    return True


def read_override_secret() -> bytes | None:
    secret_path = Path(os.environ.get("CLAUDE_AGENT_MODEL_OVERRIDE_SECRET_FILE", DEFAULT_SECRET_PATH))
    try:
        secret = secret_path.read_text().strip()
    except OSError:
        return None

    if not secret:
        return None
    return secret.encode()


def marker_signature(secret: bytes, expected_default: str, override: str, expires: str) -> str:
    message = f"expected-default={expected_default};override={override};expires={expires}"
    return hmac.new(secret, message.encode(), hashlib.sha256).hexdigest()


def marker_authorizes(prompt: str, model: str) -> bool:
    fields = parse_marker_fields(prompt)
    if not fields:
        return False
    if not validate_marker_fields(fields):
        return False

    expected_default = fields.get("expected-default")
    override = fields.get("override")
    expires = fields.get("expires")
    signature = fields.get("sig")
    if not expected_default or not override or not expires or not signature:
        return False
    if override != model:
        return False

    try:
        expires_at = int(expires)
    except ValueError:
        return False
    if time.time() > expires_at + MAX_CLOCK_SKEW_SECONDS:
        return False

    secret = read_override_secret()
    if not secret:
        return False

    expected_signature = marker_signature(secret, expected_default, override, expires)
    return hmac.compare_digest(signature, expected_signature)


def safe_agent_paths(subagent_type: object) -> list[Path]:
    if not isinstance(subagent_type, str) or not AGENT_NAME_PATTERN.fullmatch(subagent_type):
        return []

    roots = []
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        roots.append(Path(project_dir) / ".claude" / "agents")
    roots.extend([
        Path.cwd() / ".claude" / "agents",
        Path.home() / ".claude" / "agents",
    ])

    paths: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        try:
            resolved_root = root.resolve()
            path = (resolved_root / f"{subagent_type}.md").resolve()
            path.relative_to(resolved_root)
        except (OSError, ValueError):
            continue
        if path not in seen:
            seen.add(path)
            paths.append(path)
    return paths


_NOT_FOUND = object()  # sentinel: no frontmatter found


def agent_model_from_frontmatter(subagent_type: object) -> str | None | object:
    if not isinstance(subagent_type, str) or not AGENT_NAME_PATTERN.fullmatch(subagent_type):
        return _NOT_FOUND

    # 1) Check frontmatter files first — highest priority
    for path in safe_agent_paths(subagent_type):
        try:
            text = path.read_text()
        except OSError:
            continue

        if not text.startswith("---"):
            continue

        end = text.find("\n---", 3)
        if end < 0:
            continue

        frontmatter = text[3:end]
        for line in frontmatter.splitlines():
            match = MODEL_LINE_PATTERN.match(line)
            if match:
                return match.group(1)

    # 2) Fall back to built-in defaults only when no frontmatter model exists
    builtin_model = BUILTIN_AGENT_DEFAULT_MODELS.get(subagent_type)
    if builtin_model is not None:
        return builtin_model

    return _NOT_FOUND


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    if payload.get("tool_name") != "Agent":
        return 0

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0

    model = tool_input.get("model")
    if not isinstance(model, str) or not model:
        return 0

    prompt = tool_input.get("prompt")
    prompt = prompt if isinstance(prompt, str) else ""

    expected_model = agent_model_from_frontmatter(tool_input.get("subagent_type"))

    # INHERIT_MODEL in main() → allow any model
    if expected_model == INHERIT_MODEL:
        return 0

    # Frontmatter model must match exactly
    if expected_model == model:
        return 0

    subagent_type = tool_input.get("subagent_type")

    # Block unknown agents that attempt a model override
    if expected_model is _NOT_FOUND:
        reason = (
            "Agent model gate blocked this call.\n"
            f"Detected: subagent_type={subagent_type!r}, requested model={model!r}.\n"
            "Reason: no matching built-in mapping and no `.claude/agents/<subagent_type>.md` frontmatter `model:` was found.\n"
            "Do one of these next, do not keep guessing:\n"
            "1. If this is a custom agent, read its `.claude/agents/<subagent_type>.md` file and set `model` to that frontmatter value.\n"
            "2. If this is meant to be built-in, use one of these exact subagent_type values: Explore, claude-code-guide, statusline-setup, claude, general-purpose, Plan, agent-skills:code-reviewer, agent-skills:security-auditor, agent-skills:test-engineer.\n"
            "3. If no explicit override is needed, omit the `model` field from the Agent call."
        )
        emit_block(reason)
        return 0

    if marker_authorizes(prompt, model):
        return 0

    reason = (
        "Agent model gate blocked this call.\n"
        f"Detected: subagent_type={subagent_type!r}, requested model={model!r}, required model={expected_model!r}.\n"
        "Reason: Agent model overrides are disabled unless signed.\n"
        "Do one of these next, do not keep trying random models:\n"
        f"1. Retry the same Agent call with `model: {expected_model}`.\n"
        "2. Prefer omitting `model` entirely if the Agent call can be emitted without schema/UI injection.\n"
        "3. For inherit agents, any model is allowed: claude, general-purpose, Plan, agent-skills:code-reviewer, agent-skills:security-auditor, agent-skills:test-engineer.\n"
        "4. Fixed built-in defaults: Explore=haiku, claude-code-guide=haiku, statusline-setup=sonnet.\n"
        "5. For custom agents, read `.claude/agents/<subagent_type>.md` and match its frontmatter `model:` exactly.\n"
        "6. For an intentional override, add a valid signed marker: "
        "`[MODEL_OVERRIDE_APPROVED: expected-default=<model>; "
        f"override={model}; expires=<unix-seconds>; sig=<hmac-sha256>]`."
    )
    emit_block(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
