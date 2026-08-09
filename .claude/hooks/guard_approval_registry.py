#!/usr/bin/env python3
"""Deny agent writes to the human-only approval registry — the framework spec §3.B3, ADR-1.

WHY THIS EXISTS: CLAUDE.md §7 rule 2 says only the human's approval flips an
artifact to `Approved`. Nothing enforced that, because nothing distinguished a
status an agent wrote from one a human approved. The registry is the evidence
store; this hook stops an agent writing into it.

**WHAT THIS DOES NOT PREVENT — stated, not glossed (the framework spec R-1, ADR-1).**
An agent has `Write` and `Bash` over the whole filesystem, and
`.claude/settings.json` — where this hook is registered — is itself writable. So:

* This hook stops **accidental and casual** writes, loudly. That is worth having.
* Keeping the registry **outside the repo** stops a stray `git add -A` from
  committing a forged approval.
* The layer that actually **enforces** §7 rule 2 is the **CI check on a protected
  branch**, because an agent's edits to a local hook do not travel there.
* The only genuinely unforgeable option is a **GPG-signed approval** whose
  passphrase lives in the human's keychain. That imposes real setup friction and
  is an open question for the human to decide.

Claiming this hook makes approvals tamper-proof would recreate the exact
false-assurance problem the whole set exists to remove. It makes them
tamper-*evident*.

Exit codes: 0 allow, 2 block. Malformed input exits 0.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REGISTRY_ENV = "APPROVAL_LOG"
_DEFAULT_REGISTRY = Path.home() / ".claude" / "approvals" / "registry.jsonl"

# Tools that write file content directly.
_WRITE_TOOLS = frozenset({"Write", "Edit", "NotebookEdit", "MultiEdit"})


def registry_path() -> Path:
    """The registry location. Env-overridable so tests never touch the real one."""
    override = os.environ.get(_REGISTRY_ENV)
    return Path(override).expanduser() if override else _DEFAULT_REGISTRY


def _targets_registry(candidate: str, registry: Path) -> bool:
    """True when `candidate` names the registry file or its directory.

    Compared on resolved paths so a relative path, a symlink or a `..` segment
    cannot slip past a string comparison.
    """
    if not candidate:
        return False
    try:
        resolved = Path(candidate).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    registry_resolved = registry.resolve() if registry.exists() else registry
    if resolved == registry_resolved:
        return True
    # The containing directory is protected too: replacing it replaces the log.
    return resolved == registry_resolved.parent


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if payload.get("tool_name") not in _WRITE_TOOLS:
        sys.exit(0)

    tool_input = payload.get("tool_input") or {}
    candidate = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
    registry = registry_path()

    if not _targets_registry(candidate, registry):
        sys.exit(0)

    print(
        f"BLOCKED (.claude/hooks/guard_approval_registry.py, rule B3): "
        f"{candidate} is the human-only approval registry.\n"
        f"CLAUDE.md §7 rule 2: only the human's approval flips an artifact to "
        f"`Approved`. An agent writing its own approval evidence is the exact "
        f"failure this registry exists to prevent.\n"
        f"If an artifact needs approving, present the handoff and end the turn. "
        f"The human appends the entry.\n"
        f"LIMIT (stated limit): this makes forgery tamper-EVIDENT, not "
        f"impossible — an agent has Bash and could bypass a path-matching hook. "
        f"The enforcing layer is the CI check on a protected branch.",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
