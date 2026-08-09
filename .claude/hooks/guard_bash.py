#!/usr/bin/env python3
"""PreToolUse guard for Bash commands in the <PROJECT> repo.

Turns two rules that were previously prose-only — and were each violated at
least once during real work — into machine-enforced blocks:

* **A1'** destructive discard on a dirty tree. `git checkout -- <path>`,
  `git restore <path>`, `git reset --hard` and `git clean -f` silently delete
  uncommitted work. One `git checkout validation-rules.yaml` destroyed a whole
  wave's config edits and took the suite from 1297 passed to 164 failed.
  Branch switches (`git checkout -b`, `git checkout <branch>`) and `git stash`
  are NOT blocked — they do not discard.
* **A3** starting the dev backend by hand. A hand-rolled server invocation
  broke CORS, the DB connection and the schema at once because it skipped
  `.env.azure`, `PYTHONPATH=src` and `alembic upgrade`. The launcher
  `scripts/run-backend-dev.sh` exists to make that unrepeatable.

Matching is done on **command position**, not on substring presence. A naive
substring match blocked this guard's own test harness and any `grep` for the
banned token — a guard with that many false positives gets switched off, which
costs more than it saves. So heredoc bodies and quoted spans are stripped
first, then the command is split into pipeline/list segments, and a rule only
fires when the banned program is the segment's own executable.

Exit codes follow the hook contract: 0 allow, 2 block with the stderr text
shown to the model. Malformed input exits 0 — a guard that fails closed on its
own bug would be worse than the risk it covers.

Escape hatch: prefix the command with `ALLOW_DESTRUCTIVE=1` when the
discard is genuinely intended. Making the override explicit and visible in the
transcript is the point; a silent bypass would defeat the guard.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

_LAUNCHER = "scripts/run-backend-dev.sh"

# Programs that must never be launched directly (rule A3).
_BANNED_SERVERS = frozenset({"uvicorn", "hypercorn", "gunicorn"})
# `fastapi` is only a launch with these subcommands; `fastapi --help` is not.
_FASTAPI_LAUNCH_SUBCOMMANDS = frozenset({"dev", "run"})

# Heredoc bodies are data, not commands — `<<'EOF' … EOF` and `<<EOF … EOF`.
_HEREDOC_PATTERN = re.compile(
    r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1.*?^\s*\2\s*$",
    re.DOTALL | re.MULTILINE,
)
_QUOTED_SPAN_PATTERN = re.compile(r"'[^']*'|\"[^\"]*\"", re.DOTALL)
# Shell separators that start a fresh command position.
_SEGMENT_SPLIT_PATTERN = re.compile(r"\|\||&&|[;|\n()`]")
_ENV_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# Wrappers that pass their tail on to another program, so the real executable
# is further along the segment.
_TRANSPARENT_WRAPPERS = frozenset({"env", "exec", "nohup", "time", "sudo", "poetry", "uv"})


_OVERRIDE_ASSIGNMENT = "ALLOW_DESTRUCTIVE=1"


def _executable_segments(command: str) -> list[list[str]]:
    """Split a shell command into segments, each as its executable + args.

    Heredoc bodies and quoted strings are removed first so that *mentioning* a
    banned token in prose or in a test fixture is not treated as running it.
    """
    stripped = _HEREDOC_PATTERN.sub(" ", command)
    # Quotes are removed, their CONTENTS are not. Replacing a quoted span with a
    # space deleted the argument inside it, so `git checkout "config.yaml"` reached
    # the rules as a bare `git checkout` with no path — and a rule that needs a path
    # to decide saw nothing and allowed it. Quoting an argument must not be a way
    # through the gate. Prose and fixtures are still protected: a whole *command*
    # mentioned inside quotes stays inert because the segment splitter only ever
    # looks at the first token of each segment, and that token is the real
    # executable (`grep`), not the quoted text.
    stripped = _QUOTED_SPAN_PATTERN.sub(lambda m: " " + m.group(0)[1:-1] + " ", stripped)

    segments: list[list[str]] = []
    for raw in _SEGMENT_SPLIT_PATTERN.split(stripped):
        tokens = raw.split()
        # Drop leading `VAR=value` assignments and transparent wrappers so the
        # executable ends up first.
        while tokens and (
            _ENV_ASSIGNMENT_PATTERN.match(tokens[0]) or tokens[0] in _TRANSPARENT_WRAPPERS
        ):
            tokens = tokens[1:]
        if tokens:
            segments.append(tokens)
    return segments


def _program_name(token: str) -> str:
    """`.venv/bin/python` -> `python`; `/usr/bin/git` -> `git`."""
    return token.rsplit("/", maxsplit=1)[-1]


def _module_target(tokens: list[str]) -> str | None:
    """The module named by `-m <module>`, if this segment runs an interpreter."""
    if not tokens or not _program_name(tokens[0]).startswith("python"):
        return None
    for index, token in enumerate(tokens[1:-1], start=1):
        if token == "-m":
            return tokens[index + 1]
    return None


def _git_discard_reason(tokens: list[str]) -> str | None:
    """Why this `git` segment would discard uncommitted work, or None."""
    if _program_name(tokens[0]) != "git":
        return None
    args = [token for token in tokens[1:] if not token.startswith("-") or token == "--"]
    flags = {token for token in tokens[1:] if token.startswith("-")}
    subcommand = args[0] if args else ""

    if subcommand == "checkout":
        rest = tokens[tokens.index("checkout") + 1 :]
        if "-b" in flags or "-B" in flags or "--orphan" in flags:
            return None  # creating a branch, not discarding
        if "--" in rest:
            return "git checkout -- <path> discards uncommitted changes to that path"
        # A bare `git checkout <ref>` switches branches. Treat an argument that
        # looks like a path (has a separator or an extension) as a discard.
        for token in rest:
            if token.startswith("-"):
                continue
            if "/" in token or "." in token:
                return "git checkout <path> discards uncommitted changes to that path"
        return None

    if subcommand == "restore":
        # `--staged` alone only rewrites the index and is safe; adding
        # `--worktree` makes it destructive again.
        if "--staged" in flags and "--worktree" not in flags and "-W" not in flags:
            return None
        return "git restore <path> discards uncommitted changes to that path"

    if subcommand == "reset" and ("--hard" in flags or "--merge" in flags):
        return "git reset --hard discards every uncommitted change in the tree"

    if subcommand == "clean" and any(
        flag.startswith("-") and "f" in flag.lstrip("-") for flag in flags
    ):
        return "git clean -f deletes untracked files, including new source files"

    return None


def _direct_server_launch(tokens: list[str]) -> bool:
    """True when this segment launches an ASGI server directly (rule A3)."""
    program = _program_name(tokens[0])
    if program in _BANNED_SERVERS:
        return True
    if program == "fastapi":
        return any(token in _FASTAPI_LAUNCH_SUBCOMMANDS for token in tokens[1:])
    module = _module_target(tokens)
    return module in _BANNED_SERVERS


def _tree_is_dirty() -> bool:
    """True when `git status --porcelain` reports anything at all.

    Untracked files count: `git clean -f` destroys exactly those.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        # Cannot tell — assume dirty so the guard errs toward protecting work.
        return True
    return bool(result.stdout.strip())


def _block(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(2)


def _has_head_override(command: str) -> bool:
    """True only when `ALLOW_DESTRUCTIVE=1` is an env assignment on the first
    segment, the position a shell would actually apply it.

    Scoped deliberately: it waives the destructive-discard rule (A1') and nothing
    else. An escape hatch that silences every rule at once is not an escape hatch,
    it is an off switch.
    """
    first = _SEGMENT_SPLIT_PATTERN.split(command)[0]
    for token in first.split():
        if token == _OVERRIDE_ASSIGNMENT:
            return True
        if not _ENV_ASSIGNMENT_PATTERN.match(token):
            return False
    return False


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if payload.get("tool_name") != "Bash":
        sys.exit(0)

    command = str(payload.get("tool_input", {}).get("command", ""))
    if not command:
        sys.exit(0)

    # The override is a *prefix*, not a word that appears somewhere. Substring
    # matching let `echo ALLOW_DESTRUCTIVE=1 && git reset --hard` disable every rule
    # in the file: the token was never run, merely printed. It must sit in the env
    # assignment position of the first segment, exactly where a shell would apply it.
    override = _has_head_override(command)

    segments = _executable_segments(command)

    for tokens in segments:
        reason = _git_discard_reason(tokens)
        if reason and _tree_is_dirty() and not override:
            _block(
                f"BLOCKED (.claude/hooks/guard_bash.py, rule A1'): {reason}, and "
                f"the working tree has uncommitted changes.\n"
                f"This exact mistake once destroyed a wave of config edits "
                f"(suite went 1297 passed -> 164 failed).\n"
                f"Do one of these instead:\n"
                f"  1. `git stash` (reversible) or commit first, then discard;\n"
                f"  2. copy the file to a backup path if you only need its old "
                f"contents;\n"
                f"  3. if the discard is genuinely intended, re-run the command "
                f"prefixed with `ALLOW_DESTRUCTIVE=1 ` so the choice is on "
                f"the record."
            )

    for tokens in segments:
        if _direct_server_launch(tokens) and _LAUNCHER not in command:
            _block(
                f"BLOCKED (.claude/hooks/guard_bash.py, rule A3): start the dev "
                f"backend with `{_LAUNCHER}`, not a direct server command.\n"
                f"The launcher loads `.env.azure`, sets `PYTHONPATH=src`, runs "
                f"`alembic upgrade head` and passes `--reload`. Hand-rolled "
                f"invocations have broken CORS, the DB connection and the schema "
                f"at the same time."
            )

    sys.exit(0)


if __name__ == "__main__":
    main()
