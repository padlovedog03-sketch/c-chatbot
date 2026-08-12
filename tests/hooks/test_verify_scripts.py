"""The two verify scripts — the gate that decides whether a claim counts.

The gate is a mechanism like any other, so it owes the same proof as the hooks:
it must be shown to make a sound. What is pinned here is that the gate cannot
lie in the direction that matters — it must never print the word a handoff
pastes as evidence (`GREEN`) over steps that ran nothing.

WHY THIS FILE EXISTS. The template ships three of its five steps as
`echo TODO: …` placeholders. An `echo` exits 0, so the loop printed:

    OK   lint              TODO: set the lint command in scripts/verify-full.sh
    OK   format            TODO: set the format --check command
    OK   tests             TODO: set the full test command
    OK   hooks             142 passed in 8.00s
    OK   ci-examples       11 passed in 2.10s
    EXIT GATE GREEN. Paste this output in the handoff — …

Measured 2026-08-12 on this repo, exit code 0. A fresh clone could paste that
as proof a change had been linted, formatted and tested when none of the three
had happened — the framework's first truth (success reported while the truth is
elsewhere) committed by the one script whose whole job is to prevent it.

**Every case runs a COPY of the script in `tmp_path`, never the real one.**
Not hygiene — necessity. The real `verify-full.sh` runs `pytest tests/hooks/`,
which collects this file, which would run `verify-full.sh` again: unbounded
recursion. The first draft of this file did exactly that and had to be killed.
The copies replace only the step commands, so the control flow under test — the
placeholder branch, the OK/FAIL branches, the final verdict — is the real
thing, byte for byte.

Run: `python3 -m pytest tests/hooks/ -q`   (no project dependencies required)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FULL = _REPO_ROOT / "scripts" / "verify-full.sh"
_FAST = _REPO_ROOT / "scripts" / "verify-fast.sh"

#: The real step lines, so a copy can neutralise exactly the nested pytest calls
#: and nothing else. Asserted present, so this file goes red rather than quietly
#: testing a script shape that no longer exists.
_REAL_HOOK_STEP = '"hooks|python3 -m pytest tests/hooks/ -q"'
_REAL_NESTED_SUITE = "python3 -m pytest tests/hooks/ -q"
#: The second permanent (non-placeholder) step, added alongside the CI-examples
#: proof (`tests/ci/`). It is not stubbed by `_REAL_NESTED_SUITE` above because
#: it names a different directory — a copy that stubs only `_REAL_HOOK_STEP`
#: would leave this one real, and the real command fails inside `tmp_path`
#: (there is no `tests/ci/` there), turning an unrelated test red for a reason
#: that has nothing to do with what it is testing. Every case below that
#: neutralises the hooks step must neutralise this one too.
_REAL_CI_STEP = '"ci-examples|python3 -m pytest tests/ci/ -q"'
#: The nested call the second `case` block in `verify-fast.sh` runs, and the
#: text embedded inside `_REAL_CI_STEP` above. Both scripts can contain it, so
#: `_copy()` checks for it unconditionally, the same way it already does for
#: `_REAL_NESTED_SUITE`.
_REAL_CI_NESTED_SUITE = "python3 -m pytest tests/ci/ -q"
#: The third permanent step, added alongside the Scar Forge's station tracker
#: (`tests/scars/`, `scripts/scar_status.py`). Same reason as the two above:
#: an un-stubbed copy has no `tests/scars/` or `doc/scars/` to run against.
_REAL_SCAR_STEP = (
    '"scar-forge|python3 -m pytest tests/scars/ -q && python3 scripts/scar_status.py"'
)
_REAL_SCAR_NESTED_SUITE = "python3 -m pytest tests/scars/ -q"
_PLACEHOLDER_STEPS = (
    '"lint|echo TODO: set the lint command in scripts/verify-full.sh"',
    '"format|echo TODO: set the format --check command"',
    '"tests|echo TODO: set the full test command"',
)


def _run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), *args], capture_output=True, text=True, timeout=120, check=False
    )


def _copy(tmp_path: Path, source: Path, *replacements: tuple[str, str]) -> Path:
    """A runnable copy of `source` at `tmp_path/scripts/`, with substitutions applied.

    Each replacement must match exactly once — a silently-missed substitution
    would leave the nested suite in place and hang the run.
    """
    body = source.read_text(encoding="utf-8")
    for old, new in replacements:
        assert body.count(old) == 1, f"expected exactly one {old!r}, found {body.count(old)}"
        body = body.replace(old, new, 1)
    assert _REAL_NESTED_SUITE not in body, "copy still invokes the hook suite — would recurse"
    assert _REAL_CI_NESTED_SUITE not in body, "copy still invokes the ci-examples suite — would recurse"
    assert _REAL_SCAR_NESTED_SUITE not in body, "copy still invokes the scar-forge suite — would recurse"
    (tmp_path / "scripts").mkdir(exist_ok=True)
    probe = tmp_path / "scripts" / source.name
    probe.write_text(body, encoding="utf-8")
    return probe


# ---------------------------------------------------------------------------
# verify-full.sh — the exit gate
# ---------------------------------------------------------------------------


def test_the_gate_never_says_green_while_a_step_is_an_unfilled_placeholder(
    tmp_path: Path,
) -> None:
    """The core property. `GREEN` is the token a handoff pastes as evidence, so
    it must be reachable only when every step actually ran something. The three
    placeholders are left exactly as shipped; only the nested suite is stubbed.

    Injection run 2026-08-12: with the `echo TODO:` branch removed from the loop
    — the shape this script shipped in — this test and
    `test_a_placeholder_step_is_labelled_todo_not_ok` both went red, because the
    gate printed `OK` three times and then `EXIT GATE GREEN`. Reverted.
    """
    probe = _copy(
        tmp_path,
        _FULL,
        (_REAL_HOOK_STEP, '"hooks|echo 142 passed"'),
        (_REAL_CI_STEP, '"ci-examples|echo 11 passed"'),
        (_REAL_SCAR_STEP, '"scar-forge|echo 16 passed"'),
    )

    result = _run(probe)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "EXIT GATE GREEN" not in result.stdout, (
        "the gate claimed GREEN while three steps were unfilled placeholders:\n" + result.stdout
    )
    assert "EXIT GATE INCOMPLETE" in result.stdout
    assert "verified NOTHING" in result.stdout
    assert "lint" in result.stdout and "format" in result.stdout and "tests" in result.stdout


def test_a_placeholder_step_is_labelled_todo_not_ok(tmp_path: Path) -> None:
    """`OK` next to a step that ran `echo` is the lie in miniature."""
    probe = _copy(
        tmp_path,
        _FULL,
        (_REAL_HOOK_STEP, '"hooks|echo 142 passed"'),
        (_REAL_CI_STEP, '"ci-examples|echo 11 passed"'),
        (_REAL_SCAR_STEP, '"scar-forge|echo 16 passed"'),
    )

    result = _run(probe)

    # Step rows only — the trailing verdict line also says "not configured".
    todo_lines = [ln for ln in result.stdout.splitlines() if ln.startswith("  ")]
    labelled = [ln for ln in todo_lines if "not configured" in ln]
    assert len(labelled) == 3, result.stdout
    for line in labelled:
        assert line.strip().startswith("TODO"), f"placeholder step not labelled TODO: {line!r}"
        assert not line.strip().startswith("OK")


def test_a_fully_configured_gate_can_still_reach_green(tmp_path: Path) -> None:
    """The complement, without which a gate that ALWAYS withheld GREEN would
    satisfy every other test here."""
    replacements = [
        (_REAL_HOOK_STEP, '"hooks|echo hooks ran"'),
        (_REAL_CI_STEP, '"ci-examples|echo ci-examples ran"'),
        (_REAL_SCAR_STEP, '"scar-forge|echo scar-forge ran"'),
    ]
    for placeholder in _PLACEHOLDER_STEPS:
        label = placeholder.split("|", 1)[0].strip('"')
        replacements.append((placeholder, f'"{label}|echo {label} ran for real"'))
    probe = _copy(tmp_path, _FULL, *replacements)

    result = _run(probe)

    assert result.returncode == 0, result.stdout
    assert "EXIT GATE GREEN" in result.stdout
    assert "TODO" not in result.stdout
    assert "INCOMPLETE" not in result.stdout


def test_the_gate_reports_red_and_exits_1_when_a_configured_step_fails(tmp_path: Path) -> None:
    """The other half: a gate that cannot go red is decoration. A real failure
    must also outrank the INCOMPLETE verdict — red is the louder truth."""
    probe = _copy(
        tmp_path,
        _FULL,
        (_REAL_HOOK_STEP, '"hooks|false"'),
        (_REAL_CI_STEP, '"ci-examples|echo ci-examples ran"'),
        (_REAL_SCAR_STEP, '"scar-forge|echo scar-forge ran"'),
    )

    result = _run(probe)

    assert result.returncode == 1, result.stdout
    assert "EXIT GATE RED" in result.stdout
    assert "EXIT GATE GREEN" not in result.stdout
    assert "EXIT GATE INCOMPLETE" not in result.stdout


def test_the_gate_still_wires_in_the_framework_hook_suite(tmp_path: Path) -> None:
    """Asserted on the real file's text, since running it here would recurse.
    The `hooks` step is not a placeholder and must never become one: the guards
    ship with every stack, and if they go red a gate someone relies on may be
    open again."""
    body = _FULL.read_text(encoding="utf-8")
    assert _REAL_HOOK_STEP in body, "the exit gate no longer runs the framework hook suite"
    assert "echo TODO" not in _REAL_HOOK_STEP, "the hook step has decayed into a placeholder"


def test_the_gate_still_wires_in_the_ci_examples_suite(tmp_path: Path) -> None:
    """Same property, one step over. `tests/ci/` proves `ci-examples/` still
    runs what it claims to run — a proof that only means anything if the exit
    gate actually executes it on every handoff, not just when someone
    remembers to."""
    body = _FULL.read_text(encoding="utf-8")
    assert _REAL_CI_STEP in body, "the exit gate no longer runs the CI-examples proof"
    assert "echo TODO" not in _REAL_CI_STEP, "the ci-examples step has decayed into a placeholder"


def test_the_gate_still_wires_in_the_scar_forge_suite(tmp_path: Path) -> None:
    """Same property, a third step over. The Scar Forge's station tracker
    only means anything if it is actually run against this repo's real
    `doc/scars/` on every handoff."""
    body = _FULL.read_text(encoding="utf-8")
    assert _REAL_SCAR_STEP in body, "the exit gate no longer runs the scar-forge proof"
    assert "echo TODO" not in _REAL_SCAR_STEP, "the scar-forge step has decayed into a placeholder"


# ---------------------------------------------------------------------------
# verify-fast.sh — the inner loop
# ---------------------------------------------------------------------------


def test_fast_verify_refuses_to_run_with_no_paths() -> None:
    """Scoping is the entire point of the fast tier; an unscoped run is the slow
    one wearing its name. This one is safe to run for real — it exits before
    reaching any step."""
    result = _run(_FAST)
    assert result.returncode == 2
    assert "usage" in result.stderr


@pytest.mark.parametrize(
    "path",
    [
        ".claude/hooks/guard_bash.py",
        "tests/hooks/test_guard_bash_matrix.py",
        "scripts/approve.py",
        "scripts/verify_approvals.py",
        ".claude/settings.json",
    ],
)
def test_touching_any_framework_file_pulls_in_the_hook_suite(tmp_path: Path, path: str) -> None:
    """The fill-in lint/test commands know nothing about the guards, so the fast
    tier has to recognise framework paths itself.

    `.claude/settings.json` is the subtle one and was missing until 2026-08-12:
    an unregistered hook never runs, and the tests that catch exactly that are
    the ones the registering edit would otherwise skip.

    Injection run 2026-08-12: with `.claude/settings.json` removed from the
    `case` pattern, this row alone went red — editing the file that decides
    whether any guard runs at all triggered no guard test. Reverted.
    """
    probe = _copy(
        tmp_path,
        _FAST,
        (_REAL_NESTED_SUITE, "echo NESTED-HOOK-SUITE-WOULD-RUN"),
        (_REAL_CI_NESTED_SUITE, "echo NESTED-CI-SUITE-WOULD-RUN"),
        (_REAL_SCAR_NESTED_SUITE, "echo NESTED-SCAR-SUITE-WOULD-RUN"),
    )

    result = _run(probe, path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "NESTED-HOOK-SUITE-WOULD-RUN" in result.stdout, result.stdout


def test_an_unrelated_path_does_not_pay_for_the_hook_suite(tmp_path: Path) -> None:
    """The false-positive half: the fast tier stays fast for ordinary work."""
    probe = _copy(
        tmp_path,
        _FAST,
        (_REAL_NESTED_SUITE, "echo NESTED-HOOK-SUITE-WOULD-RUN"),
        (_REAL_CI_NESTED_SUITE, "echo NESTED-CI-SUITE-WOULD-RUN"),
        (_REAL_SCAR_NESTED_SUITE, "echo NESTED-SCAR-SUITE-WOULD-RUN"),
    )

    result = _run(probe, "src/some/unrelated/module.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "NESTED-HOOK-SUITE-WOULD-RUN" not in result.stdout


@pytest.mark.parametrize(
    "path",
    [
        "ci-examples/github-actions.yml",
        "ci-examples/azure-pipelines.yml",
        "tests/ci/test_ci_examples.py",
        "scripts/verify-full.sh",
        "scripts/bootstrap.sh",
    ],
)
def test_touching_a_ci_examples_file_pulls_in_the_ci_examples_suite(
    tmp_path: Path, path: str
) -> None:
    """The mirror of `test_touching_any_framework_file_pulls_in_the_hook_suite`,
    one tier over: a change to a CI example, the exit gate, or bootstrap's
    placeholder list is exactly the kind of edit that can silently desync
    `ci-examples/` from what it claims to run, so it has to pay for the proof
    at the fast tier too."""
    probe = _copy(
        tmp_path,
        _FAST,
        (_REAL_CI_NESTED_SUITE, "echo NESTED-CI-SUITE-WOULD-RUN"),
        (_REAL_NESTED_SUITE, "echo NESTED-HOOK-SUITE-WOULD-RUN"),
        (_REAL_SCAR_NESTED_SUITE, "echo NESTED-SCAR-SUITE-WOULD-RUN"),
    )

    result = _run(probe, path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "NESTED-CI-SUITE-WOULD-RUN" in result.stdout, result.stdout


def test_touching_hook_files_does_not_pull_in_the_ci_examples_suite(tmp_path: Path) -> None:
    """The two triggers are independent: the hook suite and the CI-examples
    suite each pay only for their own paths, so neither slows down for the
    other's changes."""
    probe = _copy(
        tmp_path,
        _FAST,
        (_REAL_CI_NESTED_SUITE, "echo NESTED-CI-SUITE-WOULD-RUN"),
        (_REAL_NESTED_SUITE, "echo NESTED-HOOK-SUITE-WOULD-RUN"),
        (_REAL_SCAR_NESTED_SUITE, "echo NESTED-SCAR-SUITE-WOULD-RUN"),
    )

    result = _run(probe, ".claude/hooks/guard_bash.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "NESTED-CI-SUITE-WOULD-RUN" not in result.stdout


@pytest.mark.parametrize(
    "path",
    [
        "scripts/scar_status.py",
        "tests/scars/test_scar_status.py",
        "doc/scars/SCAR-exit-gate-green-lie.md",
        "doc/templates/SCAR.md",
    ],
)
def test_touching_a_scar_forge_file_pulls_in_the_scar_forge_suite(
    tmp_path: Path, path: str
) -> None:
    """The third mirror of `test_touching_any_framework_file_pulls_in_the_hook_suite`:
    a change to the tracker, its template, or a scar record can silently
    desync the forge's mechanically-checked claims from what the tracker
    actually enforces."""
    probe = _copy(
        tmp_path,
        _FAST,
        (_REAL_SCAR_NESTED_SUITE, "echo NESTED-SCAR-SUITE-WOULD-RUN"),
        (_REAL_NESTED_SUITE, "echo NESTED-HOOK-SUITE-WOULD-RUN"),
        (_REAL_CI_NESTED_SUITE, "echo NESTED-CI-SUITE-WOULD-RUN"),
    )

    result = _run(probe, path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "NESTED-SCAR-SUITE-WOULD-RUN" in result.stdout, result.stdout


def test_touching_hook_files_does_not_pull_in_the_scar_forge_suite(tmp_path: Path) -> None:
    """Independence, the third way: the scar-forge trigger pays only for its
    own paths."""
    probe = _copy(
        tmp_path,
        _FAST,
        (_REAL_SCAR_NESTED_SUITE, "echo NESTED-SCAR-SUITE-WOULD-RUN"),
        (_REAL_NESTED_SUITE, "echo NESTED-HOOK-SUITE-WOULD-RUN"),
        (_REAL_CI_NESTED_SUITE, "echo NESTED-CI-SUITE-WOULD-RUN"),
    )

    result = _run(probe, ".claude/hooks/guard_bash.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "NESTED-SCAR-SUITE-WOULD-RUN" not in result.stdout


def test_the_fast_tier_does_not_say_ok_over_unconfigured_steps(tmp_path: Path) -> None:
    """The same honesty rule one tier down — and this is the tier that runs
    dozens of times a day, so a false OK here is repeated far more often.

    Injection run 2026-08-12: with the `todo` counter and the INCOMPLETE branch
    removed, this test alone went red — the fast tier printed `FAST VERIFY OK`
    after two steps that ran `echo`. Reverted.
    """
    probe = _copy(
        tmp_path,
        _FAST,
        (_REAL_NESTED_SUITE, "echo NESTED-HOOK-SUITE-WOULD-RUN"),
        (_REAL_CI_NESTED_SUITE, "echo NESTED-CI-SUITE-WOULD-RUN"),
        (_REAL_SCAR_NESTED_SUITE, "echo NESTED-SCAR-SUITE-WOULD-RUN"),
    )

    result = _run(probe, "tests/hooks/test_guard_bash_matrix.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "FAST VERIFY OK" not in result.stdout, result.stdout
    assert "FAST VERIFY INCOMPLETE" in result.stdout
    assert "verified NOTHING" in result.stdout
    # The trigger must still have fired — honesty about the placeholders must
    # not come at the cost of skipping the guard suite.
    assert "NESTED-HOOK-SUITE-WOULD-RUN" in result.stdout


def test_a_fully_configured_fast_tier_can_still_say_ok(tmp_path: Path) -> None:
    """The complement: with LINT and TEST filled in, OK must be reachable."""
    probe = _copy(
        tmp_path,
        _FAST,
        (_REAL_NESTED_SUITE, "echo NESTED-HOOK-SUITE-WOULD-RUN"),
        (_REAL_CI_NESTED_SUITE, "echo NESTED-CI-SUITE-WOULD-RUN"),
        (_REAL_SCAR_NESTED_SUITE, "echo NESTED-SCAR-SUITE-WOULD-RUN"),
        ('LINT=(echo "TODO: set LINT in scripts/verify-fast.sh — e.g. ruff check")',
         'LINT=(echo "lint ran")'),
        ('TEST=(echo "TODO: set TEST in scripts/verify-fast.sh — e.g. pytest -q")',
         'TEST=(echo "tests ran")'),
    )

    result = _run(probe, "tests/hooks/test_guard_bash_matrix.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "FAST VERIFY OK" in result.stdout
    assert "INCOMPLETE" not in result.stdout
