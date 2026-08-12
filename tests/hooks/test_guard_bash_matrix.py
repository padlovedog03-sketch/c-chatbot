"""`guard_bash.py` — the full block/allow matrix, both halves.

`tests/hooks/test_guard_bash_bypasses.py` pins the two bypasses that were
provably open. This file pins the ordinary behaviour around them:

* every destructive-discard shape blocks **on a dirty tree** — and the same
  commands are **allowed on a clean one**. Without the second half, a guard
  that blocks unconditionally would look correct while taxing every safe
  discard with ceremony;
* branch operations, reversible saves, and *mentions* of banned commands are
  never blocked — a guard that cries wolf gets switched off, and then it
  protects nothing;
* the hook fails open on malformed input and is actually registered in
  `.claude/settings.json`, because an unregistered hook never runs — the
  quietest possible failure.

On the originating project the dirty-tree cases silently **skipped whenever
the tree happened to be clean** — which is the state CI always checks out, so
the guard's most important rule was unverified exactly where it mattered. The
dirty state is therefore constructed here, never inherited.

Run: `python3 -m pytest tests/hooks/ -q`   (no project dependencies required)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GUARD = _REPO_ROOT / ".claude" / "hooks" / "guard_bash.py"

_EXIT_ALLOW = 0
_EXIT_BLOCK = 2

MUST_BLOCK_DIRTY_TREE = [
    # A1' — discards uncommitted work
    "git checkout -- config.yaml",
    "git checkout src/app.py",
    "git restore config.yaml",
    "git restore --worktree .",
    "git restore --staged --worktree src/",
    "git reset --hard origin/main",
    "git reset --merge",
    "git clean -fd",
    "git clean -f",
]

MUST_ALLOW = [
    # Branch operations and reversible saves are not discards.
    "git checkout -b feature/x",
    "git checkout -B main",
    "git checkout main",
    "git stash",
    "git stash pop",
    "git reset --soft HEAD~1",
    # --staged without --worktree only rewrites the index.
    "git restore --staged .",
    "git restore --staged src/app.py",
    # Ordinary work.
    "git add -A",
    "git commit -m 'feat: x'",
    "git status --porcelain",
    # Mentioning a banned command is not running it. A substring guard got
    # every one of these wrong, blocked its own test harness, and a guard with
    # that many false positives gets switched off — which costs more than it
    # saves.
    "grep -rn 'git reset --hard' doc/",
    "grep -rln 'git checkout' .",
    "echo 'git clean -f is dangerous'",
    "python3 - <<'PY'\nprint('git reset --hard is just text here')\nPY",
    # A quoted REGEX ALTERNATION. Inside quotes a `|` is data, but the segment
    # splitter used to treat it as a pipe, manufacturing a `git reset --hard`
    # segment out of the second branch and blocking a read-only search. Found
    # 2026-08-12 while grepping this very repo for leaked vocabulary.
    "grep -rnE 'foo|git reset --hard' .",
    "grep -rniE 'alpha|git checkout|beta' src/",
    "rg --json 'a;git clean -f' .",
    'grep -rE "x&&git reset --hard" .',
]


def _run_guard(
    command: str, *, tool_name: str = "Bash", cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Invoke the hook exactly as the tool runner does: JSON on stdin, exit code out."""
    payload = json.dumps({"tool_name": tool_name, "tool_input": {"command": command}})
    return subprocess.run(
        [sys.executable, str(_GUARD)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        cwd=str(cwd) if cwd else None,
    )


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, timeout=30)
    tracked = path / "tracked.txt"
    tracked.write_text("committed content\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=path, check=True, timeout=30)
    subprocess.run(
        ["git", "-c", "user.email=t@example.test", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=path,
        check=True,
        timeout=30,
    )


def _porcelain(path: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=path,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout


@pytest.fixture
def dirty_repo(tmp_path: Path) -> Path:
    """A throwaway git repo with an uncommitted change — constructed and then
    verified, because a fixture that silently produced a clean tree would turn
    every block-expecting case below into a pass for the wrong reason."""
    _init_repo(tmp_path)
    (tmp_path / "tracked.txt").write_text("uncommitted edit\n", encoding="utf-8")
    assert _porcelain(tmp_path).strip(), "fixture failed to produce a dirty tree"
    return tmp_path


@pytest.fixture
def clean_repo(tmp_path: Path) -> Path:
    """A throwaway git repo with nothing uncommitted."""
    _init_repo(tmp_path)
    assert not _porcelain(tmp_path).strip(), "fixture failed to produce a clean tree"
    return tmp_path


@pytest.mark.parametrize("command", MUST_BLOCK_DIRTY_TREE)
def test_destructive_discards_are_blocked_when_the_tree_is_dirty(
    command: str, dirty_repo: Path
) -> None:
    """Rule A1'. The guard consults `git status --porcelain` in its own cwd, so
    the dirty state is constructed here — never inherited from the real repo.

    Injection run 2026-08-12: with the `git restore` branch of
    `_git_discard_reason` deleted, exactly the three `git restore` rows of this
    matrix went red — each restore shape walked through unchallenged — while
    the checkout/reset/clean rows stayed green. Reverted."""
    result = _run_guard(command, cwd=dirty_repo)
    assert result.returncode == _EXIT_BLOCK, (
        f"expected block for {command!r}, got exit {result.returncode}: {result.stderr}"
    )
    assert "A1'" in result.stderr


@pytest.mark.parametrize("command", MUST_BLOCK_DIRTY_TREE)
def test_the_same_discards_are_allowed_on_a_clean_tree(command: str, clean_repo: Path) -> None:
    """The other half of A1', which a conditional skip never asserted at all:
    with nothing uncommitted, a discard destroys nothing and must not be
    blocked. Without this, the guard could block unconditionally and still
    look correct.

    Injection run 2026-08-12: with the `_tree_is_dirty()` condition removed
    from the block decision, ten tests went red — all nine rows of this half,
    plus the clean-tree case in `test_guard_bash_bypasses.py` — every safe
    discard taxed with ceremony — while the dirty-tree half above stayed
    green. Reverted."""
    result = _run_guard(command, cwd=clean_repo)
    assert result.returncode == _EXIT_ALLOW, (
        f"expected allow on a clean tree for {command!r}, got exit "
        f"{result.returncode}: {result.stderr}"
    )


@pytest.mark.parametrize("command", MUST_ALLOW)
def test_safe_commands_are_never_blocked_even_on_a_dirty_tree(
    command: str, dirty_repo: Path
) -> None:
    """The false-positive half. Asserted on a dirty tree deliberately — that is
    when the guard is armed, and when a false positive would actually bite.

    Injection run 2026-08-12: with `_defuse_quoted_span` reverted to the old
    `lambda m: " " + m.group(0)[1:-1] + " "` — contents kept, separators left
    live — THREE of the four quoted-alternation rows went red, and every
    block-expecting case stayed green. So the defusing removes a false positive
    without removing any tooth. Reverted.

    Three, not four: `grep -rniE 'alpha|git checkout|beta' src/` passes even
    with the bug. Measured, after a first guess at the reason turned out wrong
    — the two `|` characters split the span into THREE segments, so the
    manufactured git segment is a bare `['git', 'checkout']` carrying no
    argument at all, and a bare checkout is a branch operation rather than a
    discard. The row is kept precisely because it is the near-miss: one more
    alternation branch, or a path-shaped word in the right position, and it
    blocks too."""
    result = _run_guard(command, cwd=dirty_repo)
    assert result.returncode == _EXIT_ALLOW, (
        f"expected allow for {command!r}, got exit {result.returncode}: {result.stderr}"
    )


def test_an_env_prefix_or_transparent_wrapper_does_not_hide_a_discard(
    dirty_repo: Path,
) -> None:
    """`FOO=1 git checkout .` and `nohup git reset --hard` still run git; the
    guard strips assignments and transparent wrappers before deciding."""
    for command in (
        "FOO=bar git checkout -- config.yaml",
        "nohup git reset --hard",
        "env RELOAD=1 git clean -fd",
        "cd src && git checkout -- app.py",
    ):
        result = _run_guard(command, cwd=dirty_repo)
        assert result.returncode == _EXIT_BLOCK, f"expected block for {command!r}"


def test_rule_a3_ships_disabled_and_blocks_nothing_until_configured() -> None:
    """A3 (dev-server launches must go through the project launcher) is OFF by
    default, because this template does not know your stack and a rule that
    blocks a command nobody runs is noise. Until `_LAUNCHER` and
    `_BANNED_SERVERS` are filled in, no server-shaped command may block —
    otherwise the template would ship a false positive on day one."""
    for command in ("uvicorn app.main:app --reload", "npm run dev", "fastapi dev src/main.py"):
        result = _run_guard(command)
        assert result.returncode == _EXIT_ALLOW, (
            f"A3 is unconfigured but blocked {command!r}: {result.stderr}"
        )


def test_non_bash_tools_pass_through_untouched() -> None:
    result = _run_guard("git reset --hard", tool_name="Edit")
    assert result.returncode == _EXIT_ALLOW


def test_a_malformed_payload_fails_open_rather_than_wedging_every_bash_call() -> None:
    """A guard bug must not make the repo unusable."""
    result = subprocess.run(
        [sys.executable, str(_GUARD)],
        input="not json at all",
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == _EXIT_ALLOW


def test_the_block_message_names_the_hook_the_rule_and_the_alternatives(
    dirty_repo: Path,
) -> None:
    """A block message that reads as a puzzle gets routed around. It must say
    which hook fired, which rule, and what to do instead."""
    result = _run_guard("git reset --hard", cwd=dirty_repo)
    assert result.returncode == _EXIT_BLOCK
    assert "guard_bash.py" in result.stderr
    assert "A1'" in result.stderr
    assert "git stash" in result.stderr
    assert "ALLOW_DESTRUCTIVE=1" in result.stderr


def test_the_guard_is_registered_in_settings_json() -> None:
    """A hook file that is not wired into settings.json never runs."""
    settings = json.loads((_REPO_ROOT / ".claude" / "settings.json").read_text())
    matchers = [
        entry.get("matcher", "")
        for entry in settings["hooks"]["PreToolUse"]
        if "guard_bash.py" in json.dumps(entry)
    ]
    assert matchers, "no PreToolUse entry registers guard_bash.py"
    assert any("Bash" in matcher for matcher in matchers)
