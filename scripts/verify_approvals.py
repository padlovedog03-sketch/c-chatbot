#!/usr/bin/env python3
"""Verify every `Approval:` key in `doc/**/*.md` against the approval registry.

WHY: on the project this framework came from, 83 tracked documents claimed
`Status: Approved` and nothing distinguished a status an agent wrote from one
a human approved — which made CLAUDE.md §6 rule 2 unenforceable.

**Division of responsibility, so neither check is weakened to accommodate the
other:**

* This script owns *"an `Approval:` key that exists must resolve to a registry
  entry, and that entry must agree with the document"*.
* The CI example's first gate owns *"`Status: Approved` implies an `Approval:`
  key exists"*.

That split matters on day one: the registry is legitimately **empty** until
the human appends their first entry, so a single combined check would be
unsatisfiable by any amount of agent work — and an unsatisfiable check gets
disabled. Splitting it means each half is enforceable today.

Registry format — one JSON object per line at
`${APPROVAL_LOG:-~/.claude/approvals/registry.jsonl}`:

    {"key": "spec-payment-refunds-2026-01-15", "artifact": "doc/specs/SPEC-payment-refunds.md",
     "status": "Approved", "approved_by": "<human>",
     "approved_at": "2026-01-15T18:00:00+07:00", "evidence": "chat 2026-01-15"}

Exit 0 = every declared key resolves. Exit 1 = at least one does not.
A **missing registry with keys to check is exit 1, loudly** — never a pass by
default. A missing registry with nothing to check is exit 0, because there is
genuinely nothing to verify.

Usage:  python3 scripts/verify_approvals.py
        APPROVAL_LOG=/tmp/probe.jsonl python3 scripts/verify_approvals.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# CONFIGURATION — must agree with `scripts/approve.py` and
# `.claude/hooks/guard_approval_registry.py`; the agreement is pinned by
# `tests/hooks/test_verify_approvals.py`.
# ---------------------------------------------------------------------------
_REGISTRY_ENV = "APPROVAL_LOG"
_DEFAULT_REGISTRY = Path.home() / ".claude" / "approvals" / "registry.jsonl"

#: Where approvable documents live. `doc/templates/` and `doc/framework/` are
#: excluded on purpose: templates carry placeholder lines by design.
_DOC_DIRS = ("doc/requirements", "doc/specs", "doc/architecture", "doc/qa", "doc/tasks")

# --- The pre-registry cohort -------------------------------------------------
#
# EMPTY in this template, and it must stay empty for a project that starts
# here. The mechanism exists for a team migrating an existing repo onto the
# framework: documents genuinely approved before the registry existed can be
# listed here, drawing the line in TIME instead of backdating entries —
# because a reconstructed date is not evidence, and writing one would make a
# guess indistinguishable from a countersignature, the exact confusion the
# registry exists to remove. (The real approval wording belongs verbatim in
# each document's own `## Approval history` section.)
#
# If you populate it: freeze it, pin its size with a test, and never let a new
# document join — an exemption that can grow becomes the normal path.
_PRE_REGISTRY_ARTIFACTS: frozenset[str] = frozenset()

_APPROVAL_LINE_PATTERN = re.compile(r"^\s*(?:\*\*)?Approval(?:\*\*)?\s*:\s*(.+?)\s*$", re.MULTILINE)
_STATUS_LINE_PATTERN = re.compile(r"^\s*(?:\*\*)?Status(?:\*\*)?\s*:\s*(.+?)\s*$", re.MULTILINE)
_REQUIRED_REGISTRY_KEYS = ("key", "artifact", "status", "approved_by", "approved_at")


#: Printed on EVERY run, pass or fail. The framework's own honesty rule (a
#: mechanism must declare what it cannot prevent; overclaiming is worse than
#: having nothing) applies hardest to the check that reports on the approval
#: trail, because a green line here is the single most likely thing to be
#: mistaken for "approvals are authentic". It says only that the bookkeeping
#: agrees with itself.
_LIMIT_NOTICE = (
    "  LIMIT (stated limit): this compares documents against a registry file. It makes "
    "forgery EVIDENT, not impossible — whoever runs this could also have written the "
    "entries it reads. The enforcing layer is the CI check on a protected branch, "
    "outside the actor's reach."
)


@dataclass(frozen=True)
class Problem:
    """One unresolvable or inconsistent approval claim."""

    artifact: str
    key: str
    reason: str


def registry_path() -> Path:
    override = os.environ.get(_REGISTRY_ENV)
    return Path(override).expanduser() if override else _DEFAULT_REGISTRY


def load_registry(path: Path) -> tuple[dict[str, dict], str | None]:
    """Returns (entries by key, unreadable_reason).

    `unreadable_reason` distinguishes "registry not there" from "registry
    there but says nothing about this key" — the remedies are completely
    different (one is "the human has not approved this yet", the other is
    "your environment is not set up"), so the two must never collapse into
    one message.
    """
    if not path.exists():
        return {}, f"registry not found at {path}"
    entries: dict[str, dict] = {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {}, f"registry unreadable at {path}: {exc}"
    for line_no, line in enumerate(raw.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            entry = json.loads(stripped)
        except json.JSONDecodeError as exc:
            return {}, f"registry line {line_no} is not valid JSON: {exc}"
        missing = [k for k in _REQUIRED_REGISTRY_KEYS if not entry.get(k)]
        if missing:
            return {}, f"registry line {line_no} is missing required field(s): {missing}"
        entries[str(entry["key"])] = entry
    return entries, None


def declared_approvals() -> list[tuple[str, str, str | None]]:
    """(relative path, approval key, status) for every tracked doc that declares one."""
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "doc"],
        cwd=_REPO_ROOT,
        capture_output=True,
        check=True,
        timeout=60,
    )
    declared: list[tuple[str, str, str | None]] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", errors="surrogateescape")
        if not rel.endswith(".md"):
            continue
        if not any(rel.startswith(f"{d}/") for d in _DOC_DIRS):
            continue
        path = _REPO_ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        approval = _APPROVAL_LINE_PATTERN.search(text)
        if not approval:
            continue
        status_match = _STATUS_LINE_PATTERN.search(text)
        status = status_match.group(1).split("(")[0].strip() if status_match else None
        declared.append((rel, approval.group(1).strip().strip("`"), status))
    return declared


def verify() -> tuple[list[Problem], int, str | None]:
    """Returns (problems, number of declared keys checked, registry issue)."""
    path = registry_path()
    entries, unreadable = load_registry(path)
    declared = declared_approvals()

    if not declared:
        # Nothing claims an approval key yet, so there is nothing to resolve.
        # This is the honest state of a fresh project.
        return [], 0, unreadable

    # Grandfathered artifacts are reported but never counted as problems. They
    # are separated here, before the registry-availability check, so a missing
    # registry does not turn known-historical approvals into alarms and bury
    # the one that matters.
    to_resolve = [row for row in declared if row[0] not in _PRE_REGISTRY_ARTIFACTS]

    if not to_resolve:
        return [], len(declared), unreadable

    if unreadable:
        return (
            [
                Problem(artifact, key, f"registry unavailable: {unreadable}")
                for artifact, key, _ in to_resolve
            ],
            len(declared),
            unreadable,
        )

    problems: list[Problem] = []
    for artifact, key, status in to_resolve:
        entry = entries.get(key)
        if entry is None:
            problems.append(Problem(artifact, key, "key not found in the registry"))
            continue
        if entry.get("artifact") not in {artifact, str(Path(artifact).name)}:
            problems.append(
                Problem(
                    artifact,
                    key,
                    f"registry entry points at {entry.get('artifact')!r}, not this document",
                )
            )
        elif status and entry.get("status") != status:
            problems.append(
                Problem(
                    artifact,
                    key,
                    f"document says Status {status!r}, registry says {entry.get('status')!r}",
                )
            )
    return problems, len(declared), None


def main() -> int:
    problems, checked, registry_issue = verify()
    path = registry_path()

    print(f"approval verification — registry {path}")
    if checked == 0:
        # Printed explicitly. A run that checked nothing must not read like a
        # run that checked everything and found it clean.
        print("  0 documents declare an `Approval:` key — nothing to verify.")
        if registry_issue:
            print(f"  note: {registry_issue}")
        print("  (the CI example's first gate owns 'Status: Approved implies a key exists')")
        print(_LIMIT_NOTICE)
        return 0

    declared = declared_approvals()
    grandfathered = sorted(a for a, _, _ in declared if a in _PRE_REGISTRY_ARTIFACTS)
    print(f"  {checked} document(s) declare an `Approval:` key")
    if grandfathered:
        # Printed on every run, not hidden. An exemption nobody can see is an
        # exemption that outlives its reason.
        print(
            f"  {len(grandfathered)} grandfathered (approved before this registry "
            f"existed; their dates are preserved verbatim in each document's "
            f"`## Approval history`). Frozen set — it cannot grow."
        )
    if not problems:
        print(
            f"  every one of the {checked - len(grandfathered)} post-registry key(s) "
            f"resolves to a registry entry that agrees with it."
        )
        print(_LIMIT_NOTICE)
        return 0

    print(f"  {len(problems)} unresolved approval claim(s):")
    for problem in problems:
        print(f"    {problem.artifact}  key={problem.key!r}  — {problem.reason}")
    print("  The human appends registry entries; an agent must never write them.")
    print(_LIMIT_NOTICE)
    return 1


if __name__ == "__main__":
    sys.exit(main())
