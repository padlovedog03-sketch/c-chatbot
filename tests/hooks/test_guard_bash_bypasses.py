"""Regression tests for two bypasses that were provably open in `guard_bash.py`.

Every case here was run against the pre-fix hook first and behaved as the "before"
column says. They are pinned because both bypasses share a shape that is easy to
reintroduce: a sanitiser that is a little too eager, and a permission check that is a
little too loose.

Run: `python3 -m pytest tests/hooks/ -q`   (no project dependencies required)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "guard_bash.py"

BLOCKED = 2
ALLOWED = 0


def run(command: str, cwd: Path) -> int:
    """Invoke the hook exactly as the tool runner does: JSON on stdin, exit code out."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result.returncode


@pytest.fixture()
def dirty_repo(tmp_path: Path) -> Path:
    """A git repo with an uncommitted change.

    The discard rule only fires on a dirty tree — testing it on a clean one would
    pass for the wrong reason, which is the failure mode this whole framework is
    built to avoid.
    """
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "committed.txt").write_text("v1", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "committed.txt").write_text("v2 — uncommitted", encoding="utf-8")
    return tmp_path


def test_the_precondition_holds_or_nothing_below_proves_anything(dirty_repo: Path) -> None:
    """A plain discard on a dirty tree must block.

    If this fails, every "blocked" assertion below could be blocking for some unrelated
    reason, and the suite would be reporting a guard that is not actually the one under
    test.
    """
    assert run("git checkout .", dirty_repo) == BLOCKED


class TestQuotedPathBypass:
    """Before: the sanitiser replaced a quoted span with a single space, deleting the
    argument inside it. `git checkout "config.yaml"` reached the rules as a bare
    `git checkout` with no path, and a rule that needs a path to decide saw none and
    allowed it. Quoting an argument was a way through the gate."""

    @pytest.mark.parametrize(
        "command",
        [
            'git checkout "config.yaml"',
            "git checkout 'config.yaml'",
            'git checkout -- "src/app.py"',
        ],
    )
    def test_quoting_the_path_no_longer_hides_it(self, command: str, dirty_repo: Path) -> None:
        assert run(command, dirty_repo) == BLOCKED

    @pytest.mark.parametrize(
        "command",
        [
            "grep -rn 'git checkout' .",
            'echo "git reset --hard is dangerous"',
            "cat <<EOF\ngit reset --hard\nEOF",
        ],
    )
    def test_merely_mentioning_a_banned_command_is_still_allowed(
        self, command: str, dirty_repo: Path
    ) -> None:
        """The reason the sanitiser existed. Keeping the contents of a quoted span
        must not make prose, fixtures or heredoc bodies trip the gate — a guard that
        cries wolf gets switched off, and then it protects nothing."""
        assert run(command, dirty_repo) == ALLOWED


class TestOverrideScopeBypass:
    """Before: the override was a substring test over the whole command, so
    `echo ALLOW_DESTRUCTIVE=1 && git reset --hard` disabled every rule in the file —
    the token was never executed, merely printed. It now has to sit in the env
    assignment position of the first segment, where a shell would really apply it."""

    @pytest.mark.parametrize(
        "command",
        [
            "echo ALLOW_DESTRUCTIVE=1 && git reset --hard",
            "git reset --hard # ALLOW_DESTRUCTIVE=1",
            "echo 'ALLOW_DESTRUCTIVE=1' ; git checkout .",
        ],
    )
    def test_a_mentioned_token_no_longer_waives_the_rule(
        self, command: str, dirty_repo: Path
    ) -> None:
        assert run(command, dirty_repo) == BLOCKED

    @pytest.mark.parametrize(
        "command",
        [
            "ALLOW_DESTRUCTIVE=1 git checkout .",
            "ALLOW_DESTRUCTIVE=1 git reset --hard",
            "FOO=bar ALLOW_DESTRUCTIVE=1 git checkout .",
        ],
    )
    def test_a_real_prefix_still_waives_it(self, command: str, dirty_repo: Path) -> None:
        """The escape hatch must keep working, and must keep working after another
        assignment, because that is a shape people really type."""
        assert run(command, dirty_repo) == ALLOWED


def test_a_clean_tree_needs_no_override(tmp_path: Path) -> None:
    """The discard rule is about losing uncommitted work. With nothing to lose there
    is nothing to block, and the gate must not demand ceremony for a safe command."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    assert run("git checkout .", tmp_path) == ALLOWED
