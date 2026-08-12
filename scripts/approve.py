#!/usr/bin/env python3
"""Register the human's approval of one or more documents, by slug.

CLAUDE.md §6 rule 2: only the human's approval flips an artifact to
`Status: Approved`, and only the human may append to the approval registry
(`.claude/hooks/guard_approval_registry.py` blocks every agent `Write`/`Edit`
to it).

WHY THIS EXISTS: on the project this framework came from, the ceremony — not
the rule — was the bottleneck. Each approval was a ~25-line command composed
fresh by the assistant and pasted by the owner, which is worse on both axes
that matter: it is long enough that nobody reads it before running it, and
composing it fresh each time is how a real defect shipped (a `Status:` line
was stamped onto a document with no `## Approval history` section, and the
exit gate went red for the lost wording). A reviewed script run by the owner
is both shorter to type and safer than prose regenerated every time.

**What this script deliberately does NOT change:** the human is still the
actor. This file cannot approve anything on its own, an agent running it is
still an agent writing to the registry, and the property that matters — that
a human chose — comes from a human invoking it. Per CLAUDE.md §6 the local
guards make forgery tamper-evident rather than impossible; the real
enforcement is the CI check on the protected branch. This script changes the
typing, not the trust model.

Usage (through Claude Code's `!` prefix, or any shell):
    scripts/approve.sh --list                    # what awaits approval
    scripts/approve.sh <slug> --by <your-name>   # approve every In Review doc for that slug
    scripts/approve.sh <slug> --dry-run          # show what would happen, write nothing

There is no confirmation prompt: naming the slugs is the deliberate act, and
the first version's `confirm? [y/N]` aborted every real run because the owner
types this through Claude Code's `!` prefix, which supplies no tty.

Every candidate is validated before ANYTHING is written. One bad document
aborts the whole run, so a batch can never half-apply.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIGURATION — adapt these to your project. Everything below the line is
# the contract, not configuration.
#
# The registry contract is shared by THREE consumers: this script (writes),
# `scripts/verify_approvals.py` (verifies) and
# `.claude/hooks/guard_approval_registry.py` (denies agent writes). They must
# agree on REGISTRY_ENV and DEFAULT_REGISTRY, and
# `tests/hooks/test_verify_approvals.py` pins that agreement — change one
# without the others and a test names the drift.
# ---------------------------------------------------------------------------

#: Where approvable documents live. Must match the handoff protocol's layout;
#: `doc/templates/` and `doc/framework/` are excluded on purpose — templates
#: carry placeholder lines that must never be approvable.
DOC_DIRS = ("doc/requirements", "doc/specs", "doc/architecture", "doc/qa", "doc/tasks")

#: The status a document must be in to be approvable, out of the vocabulary
#: CLAUDE.md §5 fixes (`Draft | In Review | Approved | Done | Living`).
#: `Draft` is excluded on purpose: the pipeline's own gate is that a document
#: is reviewed before it is approved, and approving straight out of Draft
#: skips the review it names.
APPROVABLE_FROM = "In Review"
APPROVED = "Approved"

#: The section every approvable document must carry, so the approval leaves a
#: record of what it replaced.
REQUIRED_SECTION = "## Approval history"

#: The registry: one JSON object per line, entries
#: {key, artifact, status, approved_by, approved_at, evidence}.
REGISTRY_ENV = "APPROVAL_LOG"
DEFAULT_REGISTRY = Path.home() / ".claude" / "approvals" / "registry.jsonl"

#: Registry key shape. `stem` is the slugified filename, `date` is YYYY-MM-DD.
KEY_TEMPLATE = "{stem}-{date}"

#: Who approved. There is NO default name: a template that ships someone's
#: username makes every unconfigured run sign as that person, and a canned
#: signature is not a signature. Pass `--by` or export this variable once.
APPROVER_ENV = "APPROVER"

# ---------------------------------------------------------------------------
# The contract. These refusals are the product — do not parameterize them:
#   1. only git-tracked documents are approvable (untracked files are invisible
#      to every check that enumerates via `git ls-files`);
#   2. exactly one `Status:` line, or refuse (two lines means the file carries
#      a status for something other than itself);
#   3. the REQUIRED_SECTION must exist (an approval must record what it replaced);
#   4. all-or-nothing batching (a half-applied batch leaves the registry
#      disagreeing with the documents about which are approved);
#   5. no confirmation prompt (Claude Code's `!` prefix has no tty; the first
#      version's prompt aborted every real run while looking like a refusal).
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Printed on every refusal AND on every success. A mechanism must declare what
#: it cannot prevent, and overclaiming is worse than having nothing — the moment
#: this script prints "approved" is precisely when a reader is most likely to
#: believe the stamp proves a human chose. It does not. It proves a stamp was
#: applied by whoever ran this command.
LIMIT_NOTICE = (
    "LIMIT (stated limit): this script records an approval, it does not authenticate "
    "one. Anything that can run it can also write the registry, so it makes forgery "
    "EVIDENT, not impossible. The enforcing layer is the CI check on a protected "
    "branch — outside the reach of whatever is being gated."
)

#: Matches only a canonical status line — anchored, so occurrences of
#: `Status: In Review` inside prose (documents quote each other constantly)
#: are never mistaken for the document's own.
STATUS_LINE = re.compile(r"^Status: (.+)$", re.MULTILINE)
SECTION_LINE = re.compile(rf"^{re.escape(REQUIRED_SECTION)}\s*$", re.MULTILINE)


class ApprovalError(RuntimeError):
    """A candidate document cannot be approved, with the reason stated."""


@dataclass(frozen=True)
class Candidate:
    """A document that is ready to be approved, and the key it will carry."""

    path: Path
    relative: str
    key: str


def registry_path() -> Path:
    """The registry file, honouring the same override the other two consumers read."""
    override = os.environ.get(REGISTRY_ENV)
    if override:
        return Path(override).expanduser()
    return DEFAULT_REGISTRY


def tracked_documents() -> set[str]:
    """Repo-relative paths of every git-tracked markdown document under `doc/`.

    Tracked-ness is a precondition, not a detail: `verify_approvals.py` and the
    CI gates enumerate documents through `git ls-files`, so an untracked file
    is invisible to them. On the originating project a suite reported
    `125 passed` with two unallowlisted specs sitting untracked in the working
    tree, and only went red after `git add`. Approving a file those checks
    cannot see produces a registry entry nothing verifies.
    """
    result = subprocess.run(
        ["git", "ls-files", "--", "doc"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return {line for line in result.stdout.splitlines() if line.endswith(".md")}


def find_documents(slug: str, tracked: set[str]) -> list[Path]:
    """Every tracked document whose filename carries `slug`.

    Matched case-insensitively against the filename only, so a slug mentioned
    in another document's body never drags that document into the batch.
    """
    needle = slug.lower()
    matches = [
        REPO_ROOT / rel
        for rel in sorted(tracked)
        if any(rel.startswith(f"{d}/") for d in DOC_DIRS) and needle in Path(rel).name.lower()
    ]
    return matches


def read_status(text: str, relative: str) -> str:
    """The document's own canonical status, refusing anything ambiguous.

    More than one anchored `Status:` line means the document carries a status
    for something other than itself — on the originating project an
    `In Review` amendment section lived inside a file whose own line said
    `Approved`. Flipping such a file would silently change two things at once,
    so this refuses instead of guessing.
    """
    found = STATUS_LINE.findall(text)
    if not found:
        raise ApprovalError(f"{relative}: ไม่มีบรรทัด `Status:`")
    if len(found) > 1:
        raise ApprovalError(
            f"{relative}: มีบรรทัด `Status:` ขึ้นต้นบรรทัดอยู่ {len(found)} แห่ง — "
            "เอกสารหนึ่งฉบับต้องมีบรรทัดเดียว แยกส่วนแก้ไขเพิ่มเติมออกเป็นไฟล์ของมันเอง"
        )
    return found[0].strip()


def build_key(relative: str, today: str) -> str:
    """The registry key for a document: KEY_TEMPLATE over its slugified stem and the date."""
    stem = Path(relative).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    return KEY_TEMPLATE.format(stem=stem, date=today)


def validate(path: Path, tracked: set[str], today: str) -> Candidate:
    """Check every precondition for `path`, or raise `ApprovalError` naming the first failure."""
    relative = path.relative_to(REPO_ROOT).as_posix()
    if relative not in tracked:
        raise ApprovalError(
            f"{relative}: git ยังไม่ track ไฟล์นี้ — `git add` ก่อน ไม่งั้นทะเบียนจะบันทึก"
            "เอกสารที่ระบบตรวจสอบมองไม่เห็น"
        )

    text = path.read_text(encoding="utf-8")
    status = read_status(text, relative)
    if status == APPROVED:
        raise ApprovalError(f"{relative}: เป็น `Status: {APPROVED}` อยู่แล้ว — ไม่มีอะไรให้ทำ")
    if status != APPROVABLE_FROM:
        raise ApprovalError(
            f"{relative}: `Status: {status}` — อนุมัติได้เฉพาะเอกสารที่เป็น "
            f"`{APPROVABLE_FROM}` เพื่อไม่ให้ Draft ข้ามรอบรีวิวของตัวเอง"
        )
    if not SECTION_LINE.search(text):
        raise ApprovalError(
            f"{relative}: ไม่มีหัวข้อ `{REQUIRED_SECTION}` — อนุมัติไปแล้วจะไม่เหลือบันทึก"
            "ว่าคีย์นี้แทนที่ถ้อยคำใด (ความผิดพลาดจริงที่เคยทำประตูออกแดงมาแล้ว)"
        )
    return Candidate(path=path, relative=relative, key=build_key(relative, today))


def apply(candidate: Candidate, evidence: str, approved_at: str, approver: str) -> dict:
    """Stamp the document and return the registry entry to append.

    The document is written first and the registry entry is returned rather
    than written, so the caller can append every entry only after every
    document has been stamped without error.
    """
    text = candidate.path.read_text(encoding="utf-8")
    text = STATUS_LINE.sub(
        f"Status: {APPROVED}\nApproval: {candidate.key}",
        text,
        count=1,
    )
    text = SECTION_LINE.sub(
        f"{REQUIRED_SECTION}\n\n"
        f"- **{approved_at[:10]} — approved (human).** Registry key `{candidate.key}`, "
        "carried on the canonical `Approval:` line above.",
        text,
        count=1,
    )
    candidate.path.write_text(text, encoding="utf-8")
    return {
        "key": candidate.key,
        "artifact": candidate.relative,
        "status": APPROVED,
        "approved_by": approver,
        "approved_at": approved_at,
        "evidence": evidence,
    }


def list_pending(tracked: set[str]) -> list[str]:
    """Every tracked document currently awaiting approval."""
    pending = []
    for rel in sorted(tracked):
        if not any(rel.startswith(f"{d}/") for d in DOC_DIRS):
            continue
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        found = STATUS_LINE.findall(text)
        if len(found) == 1 and found[0].strip() == APPROVABLE_FROM:
            pending.append(rel)
    return pending


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code; never raises for expected failures."""
    parser = argparse.ArgumentParser(
        prog="scripts/approve.sh",
        description="Register the human's approval of documents, by slug.",
    )
    parser.add_argument("slugs", nargs="*", help="document slugs, e.g. payment-refunds")
    parser.add_argument("--list", action="store_true", help="show what awaits approval")
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="show what would be approved and write nothing",
    )
    parser.add_argument(
        "--by",
        default=os.environ.get(APPROVER_ENV, ""),
        help=f"who is approving (default: ${APPROVER_ENV}; there is no fallback name)",
    )
    parser.add_argument("--evidence", default="", help="why, recorded in the registry")
    args = parser.parse_args(argv)

    tracked = tracked_documents()

    if args.list or not args.slugs:
        pending = list_pending(tracked)
        if not pending:
            print("ไม่มีเอกสารรออนุมัติ")
            return 0
        print("รออนุมัติ:")
        for rel in pending:
            print(f"  {rel}")
        if not args.slugs:
            print("\nส่ง slug เพื่ออนุมัติ เช่น scripts/approve.sh <slug> --by <ชื่อคุณ>")
        return 0

    now = datetime.now().astimezone()
    today = now.strftime("%Y-%m-%d")

    # Resolve and validate EVERYTHING before writing anything, so a bad
    # document in a batch cannot leave the earlier ones half-applied.
    candidates: list[Candidate] = []
    problems: list[str] = []
    for slug in args.slugs:
        matches = find_documents(slug, tracked)
        if not matches:
            problems.append(f"{slug}: ไม่มีเอกสารที่ git track และชื่อไฟล์ตรงกับ slug นี้")
            continue
        for path in matches:
            try:
                candidates.append(validate(path, tracked, today))
            except ApprovalError as error:
                problems.append(str(error))

    if problems:
        print("ปฏิเสธทั้งชุด — ยังไม่ได้เขียนอะไรเลย:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(LIMIT_NOTICE, file=sys.stderr)
        return 1
    if not candidates:
        print("ปฏิเสธ — ไม่พบเอกสารที่อนุมัติได้", file=sys.stderr)
        print(LIMIT_NOTICE, file=sys.stderr)
        return 1

    print("กำลังจะอนุมัติ:")
    for candidate in candidates:
        print(f"  {candidate.relative}\n      key: {candidate.key}")

    # No confirmation prompt, deliberately. The first version asked `confirm?
    # [y/N]` and was unusable: the owner types this through Claude Code's `!`
    # prefix, which supplies no tty, so `input()` hit EOF and aborted every
    # run. It also bought nothing — naming the slugs explicitly IS the
    # deliberate act, and a prompt that cannot be answered is friction with no
    # safety. `--dry-run` exists for looking first.
    if args.dry_run:
        print("\n--dry-run: ยังไม่ได้เขียนอะไร")
        return 0

    if not args.by:
        print(
            f"ปฏิเสธ — ไม่รู้ว่าใครเป็นผู้อนุมัติ: ใส่ `--by <ชื่อคุณ>` หรือ export "
            f"{APPROVER_ENV}=<ชื่อคุณ> ไว้ครั้งเดียว (เทมเพลตนี้จงใจไม่มีชื่อ default — "
            "ลายเซ็นสำเร็จรูปไม่ใช่ลายเซ็น)",
            file=sys.stderr,
        )
        print(LIMIT_NOTICE, file=sys.stderr)
        return 1

    evidence = args.evidence or f"approved by {args.by} on {today} via scripts/approve.sh"
    approved_at = now.isoformat(timespec="seconds")
    entries = [apply(candidate, evidence, approved_at, args.by) for candidate in candidates]

    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    for entry in entries:
        print(f"อนุมัติแล้ว: {entry['artifact']}  key={entry['key']}")
    print(f"\nทะเบียน: {path}")
    print("ขั้นต่อไป: python3 scripts/verify_approvals.py แล้วค่อย commit เอกสารที่ถูกประทับ")
    print(f"\n{LIMIT_NOTICE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
