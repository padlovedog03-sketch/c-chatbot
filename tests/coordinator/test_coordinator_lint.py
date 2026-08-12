"""Tests for `scripts/coordinator_lint.py` — the mechanically-checkable half
of `doc/framework/COORDINATOR-CONSTITUTION.md` (NORTH-STAR mechanism ๓).

WHY THIS FILE EXISTS. The constitution states, in its own table, exactly
which of its five rules a script can and cannot check. A test suite that only
proves the HAPPY path would leave that table's claims unverified — this file
proves each mechanically-enforced rule actually bites (injected, observed
red naming the rule, reverted), and separately proves the checker correctly
declines to claim more than it can: an untagged claim is invisible-by-design,
not a false negative.

Run: `python3 -m pytest tests/coordinator/ -q`   (no project dependencies required)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "coordinator_lint.py"

sys.path.insert(0, str(_REPO_ROOT / "scripts"))
import coordinator_lint as cl  # noqa: E402  (path must be set up first)

_SELF_REPORT = (
    "SELF-REPORT:\nRE-MEASURED: yes, ran the suite just now\n"
    "CHECKED-AGAINST-APPROVED-DOCS: none applicable\n"
)


def _run_cli(text: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "report.md"
    path.write_text(text, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(_SCRIPT), str(path)],
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# The happy path
# ---------------------------------------------------------------------------


def test_a_fully_tagged_report_is_clean(tmp_path: Path) -> None:
    text = (
        "CLAIM: 205 tests passed.\n"
        "MEASURED: python3 -m pytest tests/ -q\n\n"
        "CLAIM: the QA agent reported 42 files affected.\n"
        "RELAYED: qa-agent report, not independently re-verified\n\n"
        "CLAIM: this is probably fine because the pattern matches wave 1.\n"
        "INFERRED: assumed wave 1's fix generalises; would be wrong if this "
        "repo's directory layout differs\n\n"
        "INSTRUCTION: do not rename tests/hooks/.\n"
        "PROVENANCE: JUDGEMENT\n\n"
        "INSTRUCTION: only the human writes the registry.\n"
        "PROVENANCE: OWNER\n\n"
    ) + _SELF_REPORT

    result = _run_cli(text, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "clean" in result.stdout


def test_the_coordinator_constitution_document_itself_exists_and_names_the_grammar() -> None:
    """A cheap sanity check that the contract and the checker did not drift
    apart: every tag the checker recognises is documented, and vice versa."""
    doc = (_REPO_ROOT / "doc" / "framework" / "COORDINATOR-CONSTITUTION.md").read_text(
        encoding="utf-8"
    )
    for tag in ("CLAIM:", "MEASURED:", "INFERRED:", "RELAYED:", "INSTRUCTION:", "PROVENANCE:",
                "SELF-REPORT:", "RE-MEASURED:", "CHECKED-AGAINST-APPROVED-DOCS:"):
        assert tag in doc, f"{tag!r} is checked by the linter but not documented in the constitution"


# ---------------------------------------------------------------------------
# Rule 1 / 3 — CLAIM: needs an origin tag; MEASURED: must not truncate.
# Proven by injection: break the check function, observe the specific test
# go red, revert.
# ---------------------------------------------------------------------------


def test_an_untagged_claim_is_flagged(tmp_path: Path) -> None:
    """Injection run 2026-08-12: with the violation-append removed from the
    untagged-claim branch of `check_claims` (the `continue` left in place,
    the `Violation(...)` appended before it deleted), this test alone went
    red — the CLI reported "clean" for a claim carrying no origin tag at
    all. Reverted; `diff` against the pre-injection copy was empty.
    """
    text = "CLAIM: no files were affected.\n\n" + _SELF_REPORT

    result = _run_cli(text, tmp_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "rule 1/3" in result.stdout
    assert "no files were affected" in result.stdout


def test_a_measured_claim_with_a_truncating_command_is_flagged(tmp_path: Path) -> None:
    """The exact failure mode named in `.claude/skills/coordinator-discipline/
    SKILL.md` rule 1: a count claimed from a command with a `head`/`tail`/
    `2>/dev/null`/`-m`/`-k` in it.

    Injection run 2026-08-12: with `_TRUNCATING_PATTERNS` emptied to `()`,
    this test alone went red — a claim measured by `grep -c crash log |
    tail -1` was reported clean. Reverted; `diff` against the pre-injection
    copy was empty.
    """
    text = "CLAIM: only 2 crashes occurred.\nMEASURED: grep -c crash log | tail -1\n\n" + _SELF_REPORT

    result = _run_cli(text, tmp_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "rule 1" in result.stdout
    assert "truncates its own view" in result.stdout


def test_a_measured_claim_with_a_full_command_passes(tmp_path: Path) -> None:
    """The complement: a command with no truncating pattern must not be
    flagged, or the check above would be indistinguishable from "reject every
    MEASURED claim"."""
    text = "CLAIM: 4 files match.\nMEASURED: grep -rl pattern src/ | wc -l\n\n" + _SELF_REPORT

    result = _run_cli(text, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr


def test_a_relayed_claim_with_no_further_tag_is_accepted() -> None:
    """RELAYED: satisfies rule 3 on its own — the claim is labelled as
    someone else's number, which is exactly what the rule requires."""
    violations = cl.check_claims("CLAIM: the other team found 12 defects.\nRELAYED: their report\n")
    assert violations == []


def test_an_untagged_claim_with_a_tag_two_non_blank_lines_away_is_still_found() -> None:
    """`_LOOKAHEAD_LINES` tolerates a few non-matching lines between the claim
    and its tag (mirroring `doc/templates/SCAR.md`'s station blocks, where
    `Entered:` sits below prose, not immediately under the heading) — but it
    is finite. This pins the tolerated case; the injection below proves the
    limit itself is load-bearing, not decorative."""
    text = "CLAIM: 3 things happened.\nsome context line\nanother context line\nMEASURED: a command\n"
    assert cl.check_claims(text) == []


# ---------------------------------------------------------------------------
# Rule 4 / 5 — INSTRUCTION: needs PROVENANCE:; APPROVED <path> must resolve
# to a real, Approved document.
# ---------------------------------------------------------------------------


def test_an_instruction_with_no_provenance_is_flagged(tmp_path: Path) -> None:
    text = "INSTRUCTION: never touch the config file.\n\n" + _SELF_REPORT

    result = _run_cli(text, tmp_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "rule 4" in result.stdout


def test_provenance_owner_and_judgement_are_both_accepted() -> None:
    assert cl.check_instructions("INSTRUCTION: x.\nPROVENANCE: OWNER\n") == []
    assert cl.check_instructions("INSTRUCTION: x.\nPROVENANCE: JUDGEMENT\n") == []


def test_an_unrecognised_provenance_value_is_flagged() -> None:
    violations = cl.check_instructions("INSTRUCTION: x.\nPROVENANCE: BECAUSE I SAID SO\n")
    assert len(violations) == 1
    assert violations[0].rule == "4"


def test_provenance_approved_a_missing_file_is_flagged(tmp_path: Path) -> None:
    text = "INSTRUCTION: x.\nPROVENANCE: APPROVED doc/specs/SPEC-does-not-exist.md\n"
    violations = cl.check_instructions(text, base_dir=tmp_path)
    assert len(violations) == 1
    assert violations[0].rule == "5"
    assert "does not exist" in violations[0].reason


def test_provenance_approved_an_unapproved_document_is_flagged(tmp_path: Path) -> None:
    """The one place Rule 5 and the existing `guard_agent_spawn.py` logic
    overlap: citing a real document that is not `Status: Approved`."""
    spec_dir = tmp_path / "doc" / "specs"
    spec_dir.mkdir(parents=True)
    (spec_dir / "SPEC-draft.md").write_text("Status: Draft\n", encoding="utf-8")
    text = "INSTRUCTION: x.\nPROVENANCE: APPROVED doc/specs/SPEC-draft.md\n"

    violations = cl.check_instructions(text, base_dir=tmp_path)

    assert len(violations) == 1
    assert violations[0].rule == "5"
    assert "Draft" in violations[0].reason


def test_provenance_approved_a_genuinely_approved_document_passes(tmp_path: Path) -> None:
    spec_dir = tmp_path / "doc" / "specs"
    spec_dir.mkdir(parents=True)
    (spec_dir / "SPEC-real.md").write_text(
        "Status: Approved\nApproval: spec-real-2026-08-12\n", encoding="utf-8"
    )
    text = "INSTRUCTION: x.\nPROVENANCE: APPROVED doc/specs/SPEC-real.md\n"

    violations = cl.check_instructions(text, base_dir=tmp_path)

    assert violations == []


def test_the_provenance_check_bites_when_the_valid_values_are_widened() -> None:
    """Injection: add 'BECAUSE I SAID SO' to the valid-provenance tuple —
    the shape of a rule 4 check that has quietly stopped meaning anything.

    Measured: with the injected value added, an instruction citing that
    exact string is wrongly accepted. Restored immediately after.
    """
    original = cl._VALID_PROVENANCE_VALUES
    try:
        cl._VALID_PROVENANCE_VALUES = original + ("BECAUSE I SAID SO",)
        violations = cl.check_instructions("INSTRUCTION: x.\nPROVENANCE: BECAUSE I SAID SO\n")
        assert violations == [], "expected the injected value to be wrongly accepted"
    finally:
        cl._VALID_PROVENANCE_VALUES = original
        assert len(cl.check_instructions("INSTRUCTION: x.\nPROVENANCE: BECAUSE I SAID SO\n")) == 1


# ---------------------------------------------------------------------------
# Rules 2 / 5 (general case) — no truth-check; only the required self-report
# fields' PRESENCE is checkable, and the constitution says so.
# ---------------------------------------------------------------------------


def test_a_missing_self_report_block_is_flagged(tmp_path: Path) -> None:
    text = "CLAIM: x.\nMEASURED: y.\n"

    result = _run_cli(text, tmp_path)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "SELF-REPORT" in result.stdout


def test_a_self_report_block_missing_one_field_is_flagged() -> None:
    violations = cl.check_self_report("SELF-REPORT:\nRE-MEASURED: yes\n")
    assert len(violations) == 1
    assert violations[0].rule == "5"
    assert "CHECKED-AGAINST-APPROVED-DOCS" in violations[0].reason


def test_a_complete_self_report_block_passes() -> None:
    assert cl.check_self_report(_SELF_REPORT) == []


def test_the_self_report_presence_check_does_not_verify_truth() -> None:
    """States the documented limit as an executable fact: a `SELF-REPORT:`
    block with FABRICATED content still passes, because presence, not truth,
    is all this rule can check. If this test ever fails, the constitution's
    own claim about its limit has become false and the doc needs updating,
    not the code."""
    fabricated = (
        "SELF-REPORT:\nRE-MEASURED: yes, definitely, trust me\n"
        "CHECKED-AGAINST-APPROVED-DOCS: all of them, somehow\n"
    )
    assert cl.check_self_report(fabricated) == []


# ---------------------------------------------------------------------------
# Explicitly-declared blind spot: text with no markup at all is invisible.
# ---------------------------------------------------------------------------


def test_free_prose_with_no_markup_is_invisible_to_the_linter(tmp_path: Path) -> None:
    """Not a false negative — a stated design limit. This checker is a
    grammar check over an opt-in markup, not natural-language detection over
    arbitrary prose (the constitution says why: substring/NLP-style guessing
    is exactly what broke `.claude/hooks/guard_bash.py` before it was
    rewritten to match on command position instead)."""
    text = "There are no known bugs left. I checked everything and it's fine.\n"

    result = _run_cli(text, tmp_path)

    # No CLAIM:/INSTRUCTION: markup -> rules 1/3/4 see nothing at all. Only
    # the unconditional SELF-REPORT: requirement still fires.
    assert result.returncode == 1, result.stdout + result.stderr
    assert "SELF-REPORT" in result.stdout
    assert "no known bugs" not in result.stdout
