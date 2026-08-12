#!/usr/bin/env python3
"""PreToolUse gate on the `Agent` (subagent-spawn) tool — the framework spec §3.A5, ADR-2.

WHY THIS EXISTS: CLAUDE.md §6 rule 2 says an implementer agent must refuse to
start when its upstream spec is not `Approved`. That was prose, and prose does
not fail. This blocks the spawn instead.

**Scope is deliberately narrow.** Only `ai-engineer` and `frontend-engineer` are
gated. Gating `Explore`, `qa`, `ba-sa`, `pm`, `Plan` or `general-purpose` would
block ordinary investigation, and a guard with false positives gets switched off
— that is the documented reason Set 1's `guard_bash.py` had to be rewritten from
substring matching to command-position matching.

**Fail-closed, with an explicit override.** When the prompt names no spec the
spawn is blocked, because a warning on a spawn is useless: by the time anyone
reads it the subagent is already running. CLAUDE.md §5 does permit "small
bugfixes may start at the engineer", so a no-spec spawn is sometimes legitimate
— hence an override token rather than a prohibition, modelled on Set 1's
`ALLOW_DESTRUCTIVE=1`: the choice becomes visible in the transcript instead
of silent.

**STATED LIMIT, not glossed (stated limit):** this reads the `Status:` line
out of a repo file that an agent can edit. It is only as strong as the approval
registry (item B3) and the CI check on a protected branch (B4). On its own it is
theatre, and the spec forbids shipping it alone.

Exit codes: 0 allow, 2 block with stderr shown to the model. Malformed input
exits 0 — a hook bug must not wedge every spawn.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Only the two implementer types. Everything else passes through untouched.
_GATED_SUBAGENT_TYPES = frozenset({"ai-engineer", "frontend-engineer"})

# The override, and what it must carry. A bare token would be a rubber stamp;
# requiring a reproduction line makes the claim checkable by a human reader.
_OVERRIDE_TOKEN = "NO_SPEC_BUGFIX:"
_MIN_OVERRIDE_REASON_CHARS = 10

# Upstream references we accept in a prompt: a bare filename or a repo path.
#
# The prefixes must match what `.claude/skills/handoff-protocol/SKILL.md` mandates,
# and each one lives in its own directory — a DESIGN document is not in `doc/specs/`.
# Keeping the two in sync matters: a prefix this pattern does not accept cannot be
# named as an upstream at all, so the gate silently demands the override token for
# work that legitimately has an approved document behind it.
_UPSTREAM_DIRS = {
    "SPEC": "doc/specs",
    "DESIGN": "doc/architecture",
    "ADR": "doc/architecture",
}
_SPEC_REFERENCE_PATTERN = re.compile(
    r"(?:doc/(?:specs|architecture)/)?((?:" + "|".join(_UPSTREAM_DIRS) + r")-[A-Za-z0-9._-]+\.md)"
)

_ALLOWED_STATUS = "Approved"
_STATUS_LINE_PATTERN = re.compile(r"^\s*(?:\*\*)?Status(?:\*\*)?\s*:\s*(.+?)\s*$", re.MULTILINE)


def _repo_root() -> Path:
    """The repo this hook lives in. `$CLAUDE_PROJECT_DIR` is not relied upon
    because the hook must also work when invoked directly by a test."""
    return Path(__file__).resolve().parents[2]


def _read_status(spec_path: Path) -> str | None:
    """The first `Status:` value in the file, or None if there is none."""
    try:
        text = spec_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    match = _STATUS_LINE_PATTERN.search(text)
    if not match:
        return None
    # Take the leading word only: the pre-B2 corpus decorates the value with
    # parentheticals and, in a few files, whole paragraphs.
    return match.group(1).split("(")[0].strip().rstrip(".").strip()


def _block(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(2)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if payload.get("tool_name") != "Agent":
        sys.exit(0)

    tool_input = payload.get("tool_input") or {}
    subagent_type = str(tool_input.get("subagent_type") or "")
    if subagent_type not in _GATED_SUBAGENT_TYPES:
        sys.exit(0)

    prompt = str(tool_input.get("prompt") or "")

    # Override path first, so a legitimate small bugfix is never blocked by a
    # spec-resolution detail.
    if _OVERRIDE_TOKEN in prompt:
        reason = prompt.split(_OVERRIDE_TOKEN, maxsplit=1)[1].strip().splitlines()
        first_line = reason[0].strip() if reason else ""
        if len(first_line) >= _MIN_OVERRIDE_REASON_CHARS:
            sys.exit(0)
        _block(
            f"BLOCKED (.claude/hooks/guard_agent_spawn.py, rule A5): "
            f"`{_OVERRIDE_TOKEN}` is present but carries no reproduction.\n"
            f"CLAUDE.md §5 allows a small bugfix to start at {subagent_type} "
            f"without a spec, but the basis has to be stated. Write "
            f"`{_OVERRIDE_TOKEN} <one-line reproduction>` "
            f"(at least {_MIN_OVERRIDE_REASON_CHARS} characters)."
        )

    references = _SPEC_REFERENCE_PATTERN.findall(prompt)
    if not references:
        _block(
            f"BLOCKED (.claude/hooks/guard_agent_spawn.py, rule A5): spawning "
            f"`{subagent_type}` with no upstream spec named in the prompt.\n"
            f"CLAUDE.md §6 rule 2: an implementer must not start without an "
            f"`Approved` upstream document.\n"
            f"Do one of these:\n"
            f"  1. name the spec in the prompt (e.g. `doc/specs/SPEC-NN-....md`);\n"
            f"  2. if this is a small bugfix that legitimately has no spec "
            f"(CLAUDE.md §6), add `{_OVERRIDE_TOKEN} <one-line reproduction>` so "
            f"the basis is on the record.\n"
            f"Only `ai-engineer` and `frontend-engineer` are gated — `qa`, "
            f"`ba-sa`, `pm`, `Explore` and the rest are never blocked."
        )

    root = _repo_root()
    problems: list[str] = []
    approved: list[str] = []
    for name in dict.fromkeys(references):  # de-duplicate, keep order
        stem = Path(name).name
        prefix = stem.split("-", 1)[0]
        spec_path = root / _UPSTREAM_DIRS[prefix] / stem
        if not spec_path.is_file():
            problems.append(f"{name}: file not found at {spec_path.relative_to(root)}")
            continue
        status = _read_status(spec_path)
        if status is None:
            problems.append(f"{name}: no `Status:` line")
        elif status != _ALLOWED_STATUS:
            problems.append(f"{name}: Status is {status!r}, not {_ALLOWED_STATUS!r}")
        else:
            approved.append(name)

    if approved:
        # At least one named spec is Approved. Extra references (a superseded
        # spec, a design doc quoted for context) must not block the spawn.
        sys.exit(0)

    _block(
        f"BLOCKED (.claude/hooks/guard_agent_spawn.py, rule A5): none of the "
        f"specs named in this `{subagent_type}` prompt is `{_ALLOWED_STATUS}`.\n"
        + "\n".join(f"  - {problem}" for problem in problems)
        + f"\nCLAUDE.md §6 rule 2: only the human's approval flips an artifact to "
        f"`{_ALLOWED_STATUS}`, and an agent must refuse to start before that.\n"
        f"If the human has authorised implementation ahead of the status flip, "
        f"say so in the prompt and use `{_OVERRIDE_TOKEN} <reason>` — do NOT edit "
        f"the spec's Status line yourself. Writing your own approval is exactly "
        f"what the human-only-approval rule exists to prevent.\n"
        f"LIMIT (stated limit): this gate reads a repo file an agent can edit. "
        f"It is only as strong as the approval registry and the CI check."
    )


if __name__ == "__main__":
    main()
