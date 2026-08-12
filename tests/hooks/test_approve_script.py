"""`scripts/approve.py` — the human's approval helper, and the refusals it owes.

CLAUDE.md §6 rule 2 says only the human's approval flips a document to
`Status: Approved`. This script shortens the typing without loosening the rule,
so what needs pinning is not the happy path (one line of `sub`) but every
refusal — each of which exists because the corresponding failure actually
happened on the project this framework came from:

* a `Status:` line stamped onto a document with no `## Approval history`
  section turned the exit gate red for the wording the key replaced being lost;
* a suite reported `125 passed` over two specs that were untracked, because
  the checks enumerate documents through `git ls-files`;
* an `In Review` amendment section lived inside a file whose own status line
  said `Approved`, so a single blind substitution would have flipped two things;
* the first version's `confirm? [y/N]` prompt aborted every real run, because
  Claude Code's `!` prefix supplies no tty.

Every test below builds the precondition and asserts the *reason*, not just the
exit code — a refusal that fires for the wrong reason is not the guard we think
we have.

Run: `python3 -m pytest tests/hooks/ -q`   (no project dependencies required)
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "approve.py"

APPROVAL_HISTORY = "## Approval history\n\n- **2026-01-01 — drafted.**\n"


def _document(status: str = "In Review", *, history: bool = True, extra: str = "") -> str:
    """A minimal document carrying the canonical status-line grammar."""
    body = f"# SPEC: probe\n\nStatus: {status}\nUpstream: none\n\n"
    if history:
        body += APPROVAL_HISTORY
    return body + extra


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real git repository with `doc/specs/`, because the script reads `git ls-files`."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "probe@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "probe"], cwd=tmp_path, check=True)
    (tmp_path / "doc" / "specs").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    # The script locates the repo root as its own parent's parent, so it must be
    # invoked from a copy sitting at scripts/ inside the fixture repo.
    (tmp_path / "scripts" / "approve.py").write_text(
        SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


def _write(repo: Path, name: str, content: str, *, track: bool = True) -> Path:
    path = repo / "doc" / "specs" / name
    path.write_text(content, encoding="utf-8")
    if track:
        subprocess.run(["git", "add", str(path)], cwd=repo, check=True)
    return path


def _run(
    repo: Path,
    *args: str,
    registry: Path | None = None,
    approver_env: str | None = None,
) -> subprocess.CompletedProcess:
    """Run the script with a scrubbed environment.

    Scrubbed, because a developer with `APPROVER` exported in their own shell
    would otherwise turn the missing-approver refusal test green for a reason
    the test never controlled.
    """
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(repo / "home"),
        "APPROVAL_LOG": str(registry or (repo / "registry.jsonl")),
    }
    if approver_env is not None:
        env["APPROVER"] = approver_env
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "approve.py"), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )


# --- the happy path, asserted on the artefacts rather than on the exit code ---


def test_approving_stamps_the_document_and_appends_one_registry_entry(repo: Path) -> None:
    path = _write(repo, "SPEC-payment-refunds.md", _document())
    registry = repo / "registry.jsonl"

    result = _run(repo, "payment-refunds", "--by", "somchai", registry=registry)

    assert result.returncode == 0, result.stderr
    text = path.read_text(encoding="utf-8")
    assert "Status: Approved" in text
    key = "spec-payment-refunds-" + date.today().isoformat()
    assert f"Approval: {key}" in text
    # The history record is the half whose absence produced the original red gate.
    assert f"Registry key `{key}`" in text
    assert text.count("Status:") == 1, "the stamp must not leave a second status line"

    entries = [json.loads(line) for line in registry.read_text(encoding="utf-8").splitlines()]
    assert len(entries) == 1
    assert entries[0]["artifact"] == "doc/specs/SPEC-payment-refunds.md"
    assert entries[0]["status"] == "Approved"
    assert entries[0]["approved_by"] == "somchai"


def test_the_approver_env_var_substitutes_for_by(repo: Path) -> None:
    """`APPROVER` exists so the owner sets their name once instead of typing it
    per approval — it must feed the registry exactly as `--by` would."""
    _write(repo, "SPEC-env-approver.md", _document())
    registry = repo / "registry.jsonl"

    result = _run(repo, "env-approver", registry=registry, approver_env="somchai")

    assert result.returncode == 0, result.stderr
    entries = [json.loads(line) for line in registry.read_text(encoding="utf-8").splitlines()]
    assert entries[0]["approved_by"] == "somchai"


# --- the refusals, each with the reason asserted ---


def test_no_approver_refuses_and_writes_nothing(repo: Path) -> None:
    """The template ships NO default approver name, deliberately.

    The original defaulted to one specific person's username, which meant every
    unconfigured run on any other machine signed the registry as that person —
    a canned signature is not a signature. The refusal has to come *after*
    validation and *before* any write, and it has to name both remedies.
    """
    path = _write(repo, "SPEC-no-approver.md", _document())
    registry = repo / "registry.jsonl"

    result = _run(repo, "no-approver", registry=registry)

    assert result.returncode == 1
    assert "--by" in result.stderr
    assert "APPROVER" in result.stderr
    assert "Status: In Review" in path.read_text(encoding="utf-8"), (
        "the document was stamped despite the refusal"
    )
    assert not registry.exists(), "a refused run must not touch the registry"


def test_untracked_document_never_becomes_a_candidate(repo: Path) -> None:
    """An untracked document is refused, and this asserts WHICH mechanism refuses it.

    `find_documents` searches only within `git ls-files`, so an untracked file
    never reaches `validate` at all — the refusal comes from the slug never
    matching, not from the tracked-ness check inside `validate`. That
    distinction is the point: on the originating project an injection run
    removed `validate`'s check and all ten tests still passed, because a test
    with this name was passing for a different reason than it claimed.
    `validate`'s own check is covered directly by
    `test_validate_refuses_an_untracked_path` below, the only way to reach it.
    """
    _write(repo, "SPEC-untracked-probe.md", _document(), track=False)

    result = _run(repo, "untracked-probe", "--by", "somchai")

    assert result.returncode == 1
    assert "ไม่มีเอกสารที่ git track" in result.stderr


def test_validate_refuses_an_untracked_path(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`validate` must not trust its caller to have filtered by tracked-ness.

    Reached only by calling it directly, because `find_documents` filters
    first. Kept rather than deleted as unreachable: it is the only statement in
    the script of *why* an untracked document must not be approved, and the
    failure it names — a registry entry pointing at a document the verification
    checks cannot enumerate — has already shipped once.
    """
    spec = importlib.util.spec_from_file_location(
        "approve_probe", repo / "scripts" / "approve.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before exec: the frozen dataclass inside resolves its own
    # module through sys.modules at class-creation time.
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPO_ROOT", repo)
    path = _write(repo, "SPEC-validate-direct.md", _document(), track=False)

    with pytest.raises(module.ApprovalError, match="git ยังไม่ track"):
        module.validate(path, tracked=set(), today="2026-01-15")


def test_document_without_approval_history_is_refused(repo: Path) -> None:
    """Injection run 2026-08-12: with `validate`'s section check deleted,
    exactly two tests went red — this one, and the batch test below (whose
    "bad" document is precisely a missing-history document). Everything else
    stayed green. Reverted."""
    _write(repo, "SPEC-no-history.md", _document(history=False))

    result = _run(repo, "no-history", "--by", "somchai")

    assert result.returncode == 1
    assert "## Approval history" in result.stderr


def test_two_status_lines_are_refused_rather_than_guessed(repo: Path) -> None:
    """An `In Review` section inside an `Approved` file — the shape that made
    the original refuse instead of guess."""
    _write(
        repo,
        "SPEC-two-status.md",
        _document(extra="\n## 0A. amendment\n\nStatus: In Review\n"),
    )

    result = _run(repo, "two-status", "--by", "somchai")

    assert result.returncode == 1
    assert "บรรทัดเดียว" in result.stderr


def test_draft_cannot_skip_its_own_review(repo: Path) -> None:
    _write(repo, "SPEC-still-draft.md", _document(status="Draft"))

    result = _run(repo, "still-draft", "--by", "somchai")

    assert result.returncode == 1
    assert "In Review" in result.stderr


def test_already_approved_document_is_refused(repo: Path) -> None:
    _write(repo, "SPEC-already-done.md", _document(status="Approved"))

    result = _run(repo, "already-done", "--by", "somchai")

    assert result.returncode == 1
    assert "อยู่แล้ว" in result.stderr


def test_a_bad_document_in_a_batch_aborts_the_whole_run(repo: Path) -> None:
    """All-or-nothing: a batch must never half-apply, or the repo lands in a state
    where some documents are approved and the registry disagrees about which.

    Injection run 2026-08-12: with the abort-on-problems block deleted (write
    what validated, report the rest), SIX tests went red — this one, plus
    `test_untracked_document_never_becomes_a_candidate`,
    `test_document_without_approval_history_is_refused`,
    `test_two_status_lines_are_refused_rather_than_guessed`,
    `test_draft_cannot_skip_its_own_review` and
    `test_already_approved_document_is_refused`. Reverted.

    That count corrects an earlier record in this file which claimed "this test
    alone went red ... every single-document refusal test stayed green, because
    each still failed through the no-candidates path". Half right, and the
    wrong half is the instructive one: the single-document cases do still exit
    1 through `if not candidates`, but they exit with the generic
    "no approvable document found" instead of the specific reason, and those
    tests assert the REASON. So the deleted block is load-bearing for the
    diagnostics of every refusal, not only for batch atomicity — which is a
    stronger property than the one originally recorded. Only this test holds
    the atomicity half (exit 1 AND nothing written)."""
    good = _write(repo, "SPEC-batch-good.md", _document())
    _write(repo, "SPEC-batch-bad.md", _document(history=False))
    registry = repo / "registry.jsonl"

    result = _run(repo, "batch-good", "batch-bad", "--by", "somchai", registry=registry)

    assert result.returncode == 1
    assert "ยังไม่ได้เขียนอะไรเลย" in result.stderr
    assert "Status: In Review" in good.read_text(encoding="utf-8"), (
        "the good doc was stamped anyway"
    )
    assert not registry.exists(), "a refused batch must not touch the registry"


def test_dry_run_reports_the_plan_and_writes_nothing(repo: Path) -> None:
    path = _write(repo, "SPEC-dry-run.md", _document())
    registry = repo / "registry.jsonl"

    result = _run(repo, "dry-run", "--dry-run", registry=registry)

    assert result.returncode == 0, result.stderr
    assert "doc/specs/SPEC-dry-run.md" in result.stdout
    assert "Status: In Review" in path.read_text(encoding="utf-8")
    assert not registry.exists()


def test_no_tty_still_approves(repo: Path) -> None:
    """The first version prompted `confirm? [y/N]` and aborted every real run.

    The owner invokes this through Claude Code's `!` prefix, which supplies no
    tty, so `input()` raised `EOFError`, the empty answer failed the y/N check,
    and the approval silently became an abort — a usability defect that looked
    exactly like a refusal. Stdin is closed here to pin the shape permanently.

    Injection run 2026-08-12: with an `input("confirm? [y/N] ")` gate restored
    before the write, five tests went red — this one and every other case that
    reaches the write path, because the pytest run itself supplies no tty
    either. This dedicated test is kept anyway: it is the only one whose name
    and explicit `stdin=subprocess.DEVNULL` state the property, so it survives
    a refactor that happens to hand the others a tty. Reverted.
    """
    path = _write(repo, "SPEC-no-tty.md", _document())
    registry = repo / "registry.jsonl"

    result = subprocess.run(
        [sys.executable, str(repo / "scripts" / "approve.py"), "no-tty", "--by", "somchai"],
        cwd=repo,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(repo / "home"),
            "APPROVAL_LOG": str(registry),
        },
    )

    assert result.returncode == 0, result.stderr
    assert "Status: Approved" in path.read_text(encoding="utf-8")
    assert registry.exists()


def test_both_the_refusal_and_the_success_state_the_limit_of_the_stamp(repo: Path) -> None:
    """The moment this prints "อนุมัติแล้ว" is the moment a reader is most
    likely to believe the stamp proves a human chose. It does not — it proves a
    stamp was applied by whoever ran the command. Saying so on the SUCCESS path
    is the part that matters; a limit stated only when something goes wrong is
    a disclaimer nobody reaches.

    Injection run 2026-08-12: with `LIMIT_NOTICE` printed on the refusal paths
    only, the success half of this test went red while the refusal half stayed
    green. Reverted.
    """
    _write(repo, "SPEC-limit-refused.md", _document(history=False))
    refused = _run(repo, "limit-refused", "--by", "somchai")
    assert refused.returncode == 1
    assert "LIMIT (stated limit)" in refused.stderr
    assert "EVIDENT, not impossible" in refused.stderr

    _write(repo, "SPEC-limit-approved.md", _document())
    approved = _run(repo, "limit-approved", "--by", "somchai")
    assert approved.returncode == 0, approved.stderr
    assert "LIMIT (stated limit)" in approved.stdout, approved.stdout
    assert "CI check on a protected branch" in approved.stdout


def test_a_slug_in_another_documents_body_does_not_drag_it_in(repo: Path) -> None:
    """Slug matching is on the filename only. Documents cite each other constantly;
    matching on content would approve whatever a spec happened to mention."""
    _write(repo, "SPEC-cited-probe.md", _document())
    citing = _write(
        repo, "SPEC-citing-other.md", _document(extra="\nSee SPEC-cited-probe.md for detail.\n")
    )

    result = _run(repo, "cited-probe", "--by", "somchai")

    assert result.returncode == 0, result.stderr
    assert "Status: In Review" in citing.read_text(encoding="utf-8")


def test_list_reports_what_awaits_approval_and_writes_nothing(repo: Path) -> None:
    _write(repo, "SPEC-pending-probe.md", _document())
    _write(repo, "SPEC-finished-probe.md", _document(status="Approved"))
    registry = repo / "registry.jsonl"

    result = _run(repo, "--list", registry=registry)

    assert result.returncode == 0, result.stderr
    assert "doc/specs/SPEC-pending-probe.md" in result.stdout
    assert "SPEC-finished-probe.md" not in result.stdout
    assert not registry.exists()


def test_every_shipped_template_satisfies_the_approval_contract() -> None:
    """The templates and the approval script must agree, or the pipeline dies
    on its first real use.

    `approve.py` refuses any document without a `## Approval history` section,
    and the handoff protocol says every artifact starts from `doc/templates/`.
    All three templates shipped WITHOUT that section, so the very first
    document anyone created the prescribed way would have been refused —
    two mechanisms, each internally consistent, disagreeing at the seam where
    nobody was looking. Found 2026-08-12 by checking the templates against the
    script's own contract rather than against each other.

    Also pins exactly one canonical `Status:` line per template, the other
    condition `validate` refuses on.

    Injection run 2026-08-12: with the `## Approval history` section removed
    from `doc/templates/spec.md` (its state before this was fixed), this test
    went red naming that file, and nothing else in the suite noticed —
    which is precisely how it shipped.
    """
    templates = sorted((Path(__file__).resolve().parents[2] / "doc" / "templates").glob("*.md"))
    assert templates, "no templates found — the handoff protocol points at this directory"
    for template in templates:
        text = template.read_text(encoding="utf-8")
        assert "\n## Approval history" in text, (
            f"{template.name} lacks '## Approval history', so approve.py will refuse every "
            f"document created from it"
        )
        status_lines = [ln for ln in text.splitlines() if ln.startswith("Status:")]
        assert len(status_lines) == 1, (
            f"{template.name} carries {len(status_lines)} canonical Status lines; "
            f"approve.py refuses anything other than exactly one"
        )
