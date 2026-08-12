#!/usr/bin/env python3
"""Grammar linter for `doc/framework/COORDINATOR-CONSTITUTION.md` (NORTH-STAR
mechanism ๓ — obligations that bind the ORCHESTRATOR, not the workers).

WHY THIS EXISTS. Every other guard in this repo governs an agent. Nothing
governed the coordinator, and the coordinator is the actor measured to be
wrong most often and caught least often by itself (สัจธรรม ๓). Two of the
constitution's five rules reduce to a checkable GRAMMAR: does a claim of a
count/absence carry an origin tag (`MEASURED:`/`INFERRED:`/`RELAYED:`), and
does a directive carry a provenance tag (`PROVENANCE: OWNER|APPROVED
<path>|JUDGEMENT`)? This script checks exactly that grammar — the same way
`scripts/verify_approvals.py` checks that an `Approval:` key resolves in the
registry without checking whether the human meant it.

**What this script does NOT do (stated, not glossed):**

* It does not verify a `MEASURED:` command was actually run, or that a
  `RELAYED:` source is real — only that the required tag is PRESENT next to
  the claim it governs, in the fixed grammar the constitution defines.
* It does not detect free-form claims that never used the `CLAIM:`/
  `INSTRUCTION:` markup at all — that text is invisible to this checker by
  design (see the constitution's own honesty section). This is a grammar
  check over an OPT-IN markup, not natural-language detection over arbitrary
  prose — the substring-matching failure that made `.claude/hooks/
  guard_bash.py` block its own test harness is exactly what this design
  avoids repeating one level up.
* Rules ๒ (never describe state from memory) and ๕'s general case (a brief
  conflicting with an approved doc's CONTENT, not just an unapproved doc)
  have no mechanical check here at all — only the required `SELF-REPORT:`
  block, whose PRESENCE and completeness is checked, never whose truth is.

Usage:
    python3 scripts/coordinator_lint.py <file>
    python3 scripts/coordinator_lint.py -            # read stdin
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

_CLAIM_RE = re.compile(r"^CLAIM:\s*(.+?)\s*$", re.MULTILINE)
_INSTRUCTION_RE = re.compile(r"^INSTRUCTION:\s*(.+?)\s*$", re.MULTILINE)
_ORIGIN_TAG_RE = re.compile(r"^(MEASURED|INFERRED|RELAYED):\s*(.+?)\s*$", re.MULTILINE)
_PROVENANCE_RE = re.compile(r"^PROVENANCE:\s*(.+?)\s*$", re.MULTILINE)

_SELF_REPORT_RE = re.compile(r"^SELF-REPORT:\s*$", re.MULTILINE)
_RE_MEASURED_RE = re.compile(r"^RE-MEASURED:\s*(.+?)\s*$", re.MULTILINE)
_CHECKED_DOCS_RE = re.compile(r"^CHECKED-AGAINST-APPROVED-DOCS:\s*(.+?)\s*$", re.MULTILINE)

#: How many lines after a `CLAIM:`/`INSTRUCTION:` line to look for its tag —
#: mirrors `doc/templates/SCAR.md`'s station blocks, where `Entered:`/`Owner:`
#: sit a blank line below the heading rather than immediately after it.
_LOOKAHEAD_LINES = 3

#: Rule 1: a `MEASURED:` command matching any of these truncates its own
#: view — the exact shapes named in `.claude/skills/coordinator-discipline/
#: SKILL.md` rule 1 (head/tail, a hard limit, a swallowed error, `-k`/`-m`
#: filtering, `--lf`).
_TRUNCATING_PATTERNS = (
    re.compile(r"\bhead\b"),
    re.compile(r"\btail\b"),
    re.compile(r"2>/dev/null"),
    re.compile(r"--max-count"),
    re.compile(r"-m\s*\d"),
    re.compile(r"-k\s"),
    re.compile(r"\[:\s*-?\d+\]"),
    re.compile(r"--lf\b|--last-failed"),
)

_VALID_PROVENANCE_VALUES = ("OWNER", "JUDGEMENT")
_APPROVED_PROVENANCE_RE = re.compile(r"^APPROVED\s+(\S+)$")


@dataclass(frozen=True)
class Violation:
    """One rule violation, with the line it was found on."""

    rule: str
    line_no: int
    reason: str


def _lookahead_tag(lines: list[str], start_index: int, tag_pattern: re.Pattern) -> re.Match | None:
    """Search up to `_LOOKAHEAD_LINES` non-blank lines after `start_index`
    for a line matching `tag_pattern`."""
    seen = 0
    for line in lines[start_index + 1 :]:
        if not line.strip():
            continue
        match = tag_pattern.match(line)
        if match:
            return match
        seen += 1
        if seen >= _LOOKAHEAD_LINES:
            break
    return None


def check_claims(text: str) -> list[Violation]:
    """Rule 1 (truncated view) and Rule 3 (unlabelled relay) — both reduce to
    the same grammar: every `CLAIM:` needs an origin tag, and if that tag is
    `MEASURED:`, the command it names must not itself truncate."""
    violations: list[Violation] = []
    lines = text.splitlines()
    tag_line_pattern = re.compile(r"^(MEASURED|INFERRED|RELAYED):\s*(.*)$")

    for match in _CLAIM_RE.finditer(text):
        line_no = text.count("\n", 0, match.start()) + 1
        tag_match = _lookahead_tag(lines, line_no - 1, tag_line_pattern)
        if tag_match is None:
            violations.append(
                Violation(
                    rule="1/3",
                    line_no=line_no,
                    reason=(
                        f"CLAIM {match.group(1)!r} has no MEASURED:/INFERRED:/RELAYED: tag "
                        f"within {_LOOKAHEAD_LINES} lines — an untagged claim of a count or "
                        f"absence is exactly what rule 1 (unseen truncation) and rule 3 "
                        f"(unlabelled relay) both forbid"
                    ),
                )
            )
            continue
        tag_kind, tag_value = tag_match.group(1), tag_match.group(2)
        if tag_kind == "MEASURED":
            for pattern in _TRUNCATING_PATTERNS:
                if pattern.search(tag_value):
                    violations.append(
                        Violation(
                            rule="1",
                            line_no=line_no,
                            reason=(
                                f"CLAIM {match.group(1)!r} is MEASURED by a command that "
                                f"truncates its own view ({pattern.pattern!r} matched in "
                                f"{tag_value!r}) — rule 1 forbids claiming a count or absence "
                                f"from a view that could not have seen all of it"
                            ),
                        )
                    )
    return violations


def check_instructions(text: str, base_dir: Path = _REPO_ROOT) -> list[Violation]:
    """Rule 4: every `INSTRUCTION:` needs a `PROVENANCE:` tag naming OWNER,
    an APPROVED document, or the coordinator's own JUDGEMENT. If APPROVED is
    named, the path must exist and its document must say `Status: Approved`
    — reusing the same check `.claude/hooks/guard_agent_spawn.py` already
    performs for one narrow case (spawning an implementer).

    `base_dir` resolves `APPROVED <path>` — overridable so tests can point it
    at a scratch directory instead of this repo's real `doc/`.
    """
    violations: list[Violation] = []
    lines = text.splitlines()

    for match in _INSTRUCTION_RE.finditer(text):
        line_no = text.count("\n", 0, match.start()) + 1
        prov_match = _lookahead_tag(lines, line_no - 1, _PROVENANCE_RE)
        if prov_match is None:
            violations.append(
                Violation(
                    rule="4",
                    line_no=line_no,
                    reason=(
                        f"INSTRUCTION {match.group(1)!r} has no PROVENANCE: tag within "
                        f"{_LOOKAHEAD_LINES} lines — rule 4 requires every instruction to name "
                        f"its origin: OWNER, an APPROVED document, or the coordinator's own "
                        f"JUDGEMENT"
                    ),
                )
            )
            continue
        value = prov_match.group(1).strip()
        approved_match = _APPROVED_PROVENANCE_RE.match(value)
        if value in _VALID_PROVENANCE_VALUES:
            continue
        if approved_match is None:
            violations.append(
                Violation(
                    rule="4",
                    line_no=line_no,
                    reason=(
                        f"PROVENANCE: {value!r} is not OWNER, JUDGEMENT, or "
                        f"'APPROVED <path>' — an unrecognised provenance value is as "
                        f"uncheckable as no value at all"
                    ),
                )
            )
            continue
        doc_path = base_dir / approved_match.group(1)
        if not doc_path.is_file():
            violations.append(
                Violation(
                    rule="5",
                    line_no=line_no,
                    reason=(
                        f"PROVENANCE: APPROVED {approved_match.group(1)!r} names a file that "
                        f"does not exist at {doc_path} — an instruction cannot outrank a "
                        f"document that is not there"
                    ),
                )
            )
            continue
        doc_text = doc_path.read_text(encoding="utf-8")
        status_match = re.search(r"^Status:\s*(.+?)\s*$", doc_text, re.MULTILINE)
        status = status_match.group(1).split("(")[0].strip() if status_match else None
        if status != "Approved":
            violations.append(
                Violation(
                    rule="5",
                    line_no=line_no,
                    reason=(
                        f"PROVENANCE: APPROVED {approved_match.group(1)!r} but that document's "
                        f"own Status is {status!r}, not 'Approved' — rule 5 says the "
                        f"coordinator's instruction never outranks an approved document, and an "
                        f"unapproved one has nothing to outrank with"
                    ),
                )
            )
    return violations


def check_self_report(text: str) -> list[Violation]:
    """Rules ๒ and ๕ (general case) have no mechanical truth-check — this
    checks only that the required self-report FIELDS exist and are filled,
    per the constitution's honesty section."""
    violations: list[Violation] = []
    if not _SELF_REPORT_RE.search(text):
        violations.append(
            Violation(
                rule="2/5",
                line_no=0,
                reason=(
                    "no `SELF-REPORT:` block found — rules 2 and 5 have no mechanical "
                    "truth-check, so the constitution requires this block as the declared "
                    "substitute; its absence is itself the checkable failure"
                ),
            )
        )
        return violations

    if not _RE_MEASURED_RE.search(text):
        violations.append(
            Violation(
                rule="2",
                line_no=0,
                reason="SELF-REPORT: block has no `RE-MEASURED:` line",
            )
        )
    if not _CHECKED_DOCS_RE.search(text):
        violations.append(
            Violation(
                rule="5",
                line_no=0,
                reason="SELF-REPORT: block has no `CHECKED-AGAINST-APPROVED-DOCS:` line",
            )
        )
    return violations


def lint(text: str, base_dir: Path = _REPO_ROOT) -> list[Violation]:
    return check_claims(text) + check_instructions(text, base_dir) + check_self_report(text)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: coordinator_lint.py <file>|-", file=sys.stderr)
        return 2
    text = sys.stdin.read() if argv[0] == "-" else Path(argv[0]).read_text(encoding="utf-8")

    violations = lint(text)
    if not violations:
        print("coordinator-lint: clean — every CLAIM/INSTRUCTION tagged, SELF-REPORT complete.")
        print(
            "LIMIT (stated limit): this checks grammar (a tag is present, in the right shape), "
            "never truth (that the tagged command was really run, or the tagged source is real). "
            "An independent read of the raw evidence is still required — this does not replace it."
        )
        return 0

    print(f"coordinator-lint: {len(violations)} violation(s):")
    for v in sorted(violations, key=lambda x: x.line_no):
        where = f"line {v.line_no}" if v.line_no else "document"
        print(f"  rule {v.rule} ({where}): {v.reason}")
    print(
        "LIMIT (stated limit): this checks grammar, never truth. See doc/framework/"
        "COORDINATOR-CONSTITUTION.md for what each rule can and cannot mechanically catch."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
