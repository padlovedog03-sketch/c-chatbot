"""`guard_approval_registry.py` — the deny hook on the human-only registry.

What is proven here is the **mechanism**: a write aimed at the registry (by any
path spelling) is denied, a write anywhere else is allowed, and the denial
message admits its own limit. Not proven, because it is not true: that
approvals are unforgeable. An agent has `Bash`, so the enforcing layer is CI on
a protected branch — a test claiming more would be the false assurance this
whole set exists to remove.

Every case uses a temporary registry via `APPROVAL_LOG`, so the real
`~/.claude/approvals/registry.jsonl` is never touched.

Run: `python3 -m pytest tests/hooks/ -q`   (no project dependencies required)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DENY_HOOK = _REPO_ROOT / ".claude" / "hooks" / "guard_approval_registry.py"
_REGISTRY_ENV = "APPROVAL_LOG"

_EXIT_ALLOW = 0
_EXIT_BLOCK = 2


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    path = tmp_path / "registry.jsonl"
    path.write_text('{"key": "probe"}\n', encoding="utf-8")
    return path


def _run_hook(
    tool_name: str,
    registry: Path,
    *,
    file_path: str | None = None,
    notebook_path: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env[_REGISTRY_ENV] = str(registry)
    tool_input: dict[str, str] = {}
    if file_path is not None:
        tool_input["file_path"] = file_path
    if notebook_path is not None:
        tool_input["notebook_path"] = notebook_path
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
    return subprocess.run(
        [sys.executable, str(_DENY_HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=env,
    )


@pytest.mark.parametrize("tool_name", ["Write", "Edit", "MultiEdit", "NotebookEdit"])
def test_a_write_to_the_registry_is_denied_for_every_write_tool(
    tool_name: str, registry: Path
) -> None:
    """Injection run 2026-08-12: with `_WRITE_TOOLS` narrowed to `{"Write"}`,
    four tests went red — the Edit/MultiEdit/NotebookEdit rows of this matrix
    plus the `notebook_path` case below — meaning three tools could then write
    the registry unchallenged. Everything else stayed green. Reverted."""
    result = _run_hook(tool_name, registry, file_path=str(registry))
    assert result.returncode == _EXIT_BLOCK, result.stdout
    assert str(registry) in result.stderr
    assert "rule B3" in result.stderr


def test_a_notebook_write_via_notebook_path_is_also_denied(registry: Path) -> None:
    """`NotebookEdit` names its target `notebook_path`, not `file_path` — a hook
    that only read `file_path` would wave every notebook write through."""
    result = _run_hook("NotebookEdit", registry, notebook_path=str(registry))
    assert result.returncode == _EXIT_BLOCK


def test_the_deny_message_states_its_own_limit(registry: Path) -> None:
    """A guard that overstates what it prevents is worse than none, because the
    reader stops looking for the real enforcement point. The message must say
    tamper-EVIDENT — not tamper-proof — and point at CI."""
    result = _run_hook("Write", registry, file_path=str(registry))
    assert "tamper-EVIDENT" in result.stderr
    assert "CI" in result.stderr


def test_a_relative_or_dotted_path_to_the_registry_is_still_denied(
    registry: Path, tmp_path: Path
) -> None:
    """Paths are compared resolved, so `..`-style evasion of a string match
    does not work.

    Injection run 2026-08-12: with `_targets_registry` downgraded to a raw
    string comparison (`candidate == str(registry)`), this test and the
    parent-directory test went red — the dotted spelling walked straight past
    the guard — while the straight-path matrix above stayed green, which is
    exactly why these two cases exist. Reverted."""
    (tmp_path / "subdir").mkdir(exist_ok=True)
    sneaky = str(tmp_path / "subdir" / ".." / "registry.jsonl")
    result = _run_hook("Write", registry, file_path=sneaky)
    assert result.returncode == _EXIT_BLOCK


def test_the_registry_directory_is_protected_too(registry: Path, tmp_path: Path) -> None:
    """Replacing the directory replaces the log, so aiming a Write at the
    parent is the same attack with one fewer path segment."""
    result = _run_hook("Write", registry, file_path=str(tmp_path))
    assert result.returncode == _EXIT_BLOCK


def test_writes_to_any_other_path_are_allowed(registry: Path, tmp_path: Path) -> None:
    """A guard that blocked ordinary writes would be removed within the hour."""
    for candidate in (
        str(_REPO_ROOT / "doc" / "specs" / "SPEC-anything.md"),
        str(tmp_path / "unrelated.txt"),
        str(_REPO_ROOT / "CLAUDE.md"),
    ):
        result = _run_hook("Write", registry, file_path=candidate)
        assert result.returncode == _EXIT_ALLOW, f"{candidate}: {result.stderr}"


def test_a_read_only_tool_is_not_blocked(registry: Path) -> None:
    result = _run_hook("Read", registry, file_path=str(registry))
    assert result.returncode == _EXIT_ALLOW


def test_a_malformed_payload_fails_open(registry: Path) -> None:
    """A hook bug must not wedge every file write in the repo."""
    result = subprocess.run(
        [sys.executable, str(_DENY_HOOK)],
        input="not json",
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == _EXIT_ALLOW


def test_the_deny_hook_is_registered_in_settings_json() -> None:
    """A hook file that is not wired into settings.json never runs — the
    quietest possible failure."""
    settings = json.loads((_REPO_ROOT / ".claude" / "settings.json").read_text())
    blob = json.dumps(settings)
    assert "guard_approval_registry.py" in blob
    matchers = [
        entry.get("matcher", "")
        for entry in settings["hooks"]["PreToolUse"]
        if "guard_approval_registry.py" in json.dumps(entry)
    ]
    assert matchers, "no PreToolUse entry registers the deny hook"
    for tool in ("Write", "Edit", "NotebookEdit"):
        assert any(tool in matcher for matcher in matchers), (
            f"the deny hook is not matched on {tool}: {matchers}"
        )
