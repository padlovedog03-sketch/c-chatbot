"""`scripts/verify_approvals.py` — every declared `Approval:` key must resolve.

The honest framing of what is tested here, because it is easy to overclaim:
this proves the **mechanism** works — a declared key resolves, a missing key
fails, an absent registry fails loudly rather than passing by default. It does
**not** prove approvals are unforgeable. An agent has `Bash`, and
`.claude/settings.json` is itself writable, so the enforcing layer is CI on a
protected branch. A test claiming more than that would be the false assurance
this whole set removes.

Every case uses a temporary registry via `APPROVAL_LOG`, so the real
`~/.claude/approvals/registry.jsonl` is never read or written.

Run: `python3 -m pytest tests/hooks/ -q`   (no project dependencies required)
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VERIFIER_PATH = _REPO_ROOT / "scripts" / "verify_approvals.py"
_APPROVE_PATH = _REPO_ROOT / "scripts" / "approve.py"
_DENY_HOOK_PATH = _REPO_ROOT / ".claude" / "hooks" / "guard_approval_registry.py"
_REGISTRY_ENV = "APPROVAL_LOG"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verifier = _load(_VERIFIER_PATH, "framework_verify_approvals")


def _entry(**overrides) -> dict:
    entry = {
        "key": "probe-key-1",
        "artifact": "doc/specs/SPEC-probe.md",
        "status": "Approved",
        "approved_by": "human",
        "approved_at": "2026-01-15T18:00:00+07:00",
        "evidence": "chat 2026-01-15",
    }
    entry.update(overrides)
    return entry


def _write_registry(tmp_path: Path, *entries: dict) -> Path:
    path = tmp_path / "registry.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The registry contract has three consumers. They must agree, or an approval
# recorded by one is invisible to the others.
# ---------------------------------------------------------------------------


def test_the_three_consumers_agree_on_the_registry_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`approve.py` writes the registry, `verify_approvals.py` verifies it, and
    `guard_approval_registry.py` denies agent writes to it. If any one of them
    reads a different env var or a different default path, the failure is
    silent in the worst way: approvals land in a file nothing checks, and the
    deny hook protects a file nothing writes.
    """
    approve = _load(_APPROVE_PATH, "framework_approve_contract_probe")
    deny = _load(_DENY_HOOK_PATH, "framework_deny_hook_contract_probe")

    # Same env var name…
    assert approve.REGISTRY_ENV == verifier._REGISTRY_ENV == deny._REGISTRY_ENV

    # …same default when it is unset…
    monkeypatch.delenv(_REGISTRY_ENV, raising=False)
    assert approve.registry_path() == verifier.registry_path() == deny.registry_path()

    # …and the same resolution when it is set.
    probe = tmp_path / "probe.jsonl"
    monkeypatch.setenv(_REGISTRY_ENV, str(probe))
    assert approve.registry_path() == verifier.registry_path() == deny.registry_path() == probe


# ---------------------------------------------------------------------------
# Resolution, and the two failure modes stay distinct.
# ---------------------------------------------------------------------------


def test_a_declared_key_present_in_the_registry_resolves(tmp_path: Path) -> None:
    registry = _write_registry(tmp_path, _entry())
    entries, unreadable = verifier.load_registry(registry)
    assert unreadable is None
    assert entries["probe-key-1"]["approved_by"] == "human"


def test_a_key_absent_from_the_registry_is_reported_as_not_found(tmp_path: Path) -> None:
    registry = _write_registry(tmp_path, _entry(key="some-other-key"))
    entries, unreadable = verifier.load_registry(registry)
    assert unreadable is None
    assert "probe-key-1" not in entries


def test_an_absent_registry_is_distinguishable_from_a_missing_key(tmp_path: Path) -> None:
    """The remedies differ completely — one is "the human has not approved this
    yet", the other is "your environment is not set up" — so the two must never
    collapse into one message."""
    entries, unreadable = verifier.load_registry(tmp_path / "absent.jsonl")
    assert entries == {}
    assert unreadable is not None
    assert "not found" in unreadable


def test_a_registry_line_missing_a_required_field_is_rejected_not_ignored(
    tmp_path: Path,
) -> None:
    """A half-written entry must not silently count as an approval."""
    registry = _write_registry(tmp_path, _entry(approved_by=""))
    entries, unreadable = verifier.load_registry(registry)
    assert entries == {}
    assert unreadable is not None
    assert "missing required field" in unreadable


def test_malformed_json_in_the_registry_fails_loudly(tmp_path: Path) -> None:
    registry = tmp_path / "registry.jsonl"
    registry.write_text('{"key": "broken"\n', encoding="utf-8")
    entries, unreadable = verifier.load_registry(registry)
    assert entries == {}
    assert "not valid JSON" in (unreadable or "")


def test_comment_and_blank_lines_are_skipped_not_treated_as_entries(tmp_path: Path) -> None:
    registry = tmp_path / "registry.jsonl"
    registry.write_text(
        "# human-only append-only approval log\n\n" + json.dumps(_entry()) + "\n",
        encoding="utf-8",
    )
    entries, unreadable = verifier.load_registry(registry)
    assert unreadable is None
    assert set(entries) == {"probe-key-1"}


# ---------------------------------------------------------------------------
# An unavailable registry never passes by default.
# ---------------------------------------------------------------------------


def test_the_verifier_states_plainly_when_it_checked_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A verifier that printed nothing when it checked nothing would be
    indistinguishable from one that verified every document successfully — the
    silent-failure shape this framework exists to remove.

    The "nothing declared" state is constructed rather than read from the repo:
    on the originating project, a version of this test that asserted against
    the real tree broke the moment a migration added 31 `Approval:` lines —
    it had been measuring the environment rather than the behaviour.
    """
    monkeypatch.setattr(verifier, "declared_approvals", lambda: [])
    monkeypatch.setenv(_REGISTRY_ENV, str(tmp_path / "absent.jsonl"))
    problems, checked, issue = verifier.verify()
    assert (problems, checked) == ([], 0)
    assert issue is not None, (
        "the missing registry must still be reported even when there is nothing "
        "to verify — otherwise a broken environment looks like a clean run"
    )


def test_declared_keys_with_an_unavailable_registry_are_problems_not_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Injection run 2026-08-12: with the `if unreadable:` branch in `verify()`
    deleted (fall through to resolving against the empty dict), the reason
    degraded to `key not found` — this test and the CLI test below went red on
    the reason text, nothing else did. Reverted. That wording matters because
    "not found" sends the reader to the human, while "unavailable" sends them
    to their environment."""
    monkeypatch.setattr(
        verifier,
        "declared_approvals",
        lambda: [("doc/specs/SPEC-probe.md", "probe-key-1", "Approved")],
    )
    monkeypatch.setenv(_REGISTRY_ENV, str(tmp_path / "absent.jsonl"))
    problems, checked, _ = verifier.verify()
    assert checked == 1
    assert len(problems) == 1
    assert "registry unavailable" in problems[0].reason


def test_a_registry_entry_pointing_at_a_different_artifact_is_a_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reusing one approval key across documents would let a single human
    approval silently authorise a second artifact.

    Injection run 2026-08-12: with the artifact cross-check deleted (resolve on
    the key alone), this test alone went red — one registry entry then vouched
    for any document that quoted its key, which is forgery by copy-paste and
    needs no privileges at all. Reverted."""
    registry = _write_registry(tmp_path, _entry(artifact="doc/specs/SPEC-other.md"))
    monkeypatch.setattr(
        verifier,
        "declared_approvals",
        lambda: [("doc/specs/SPEC-probe.md", "probe-key-1", "Approved")],
    )
    monkeypatch.setenv(_REGISTRY_ENV, str(registry))
    problems, checked, _ = verifier.verify()
    assert checked == 1
    assert "points at" in problems[0].reason


def test_a_status_disagreement_between_document_and_registry_is_a_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = _write_registry(tmp_path, _entry(status="Done"))
    monkeypatch.setattr(
        verifier,
        "declared_approvals",
        lambda: [("doc/specs/SPEC-probe.md", "probe-key-1", "Approved")],
    )
    monkeypatch.setenv(_REGISTRY_ENV, str(registry))
    problems, _, _ = verifier.verify()
    assert "registry says" in problems[0].reason


def test_a_fully_consistent_declaration_produces_no_problems(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The complement. Without it, a verifier that reports everything as a
    problem would pass every test above."""
    registry = _write_registry(tmp_path, _entry())
    monkeypatch.setattr(
        verifier,
        "declared_approvals",
        lambda: [("doc/specs/SPEC-probe.md", "probe-key-1", "Approved")],
    )
    monkeypatch.setenv(_REGISTRY_ENV, str(registry))
    problems, checked, issue = verifier.verify()
    assert (problems, checked, issue) == ([], 1, None)


# ---------------------------------------------------------------------------
# The CLI, end to end, in a constructed repo — never against this one, whose
# approval state must not decide whether a test passes.
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_repo(tmp_path: Path) -> Path:
    """A git repo with one tracked spec declaring an `Approval:` key."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "doc" / "specs").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "verify_approvals.py").write_text(
        _VERIFIER_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    doc = tmp_path / "doc" / "specs" / "SPEC-probe.md"
    doc.write_text(
        "# SPEC: probe\n\nStatus: Approved\nApproval: probe-key-1\nUpstream: none\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    return tmp_path


def _run_cli(repo: Path, registry: Path) -> subprocess.CompletedProcess[str]:
    import os

    env = dict(os.environ)
    env[_REGISTRY_ENV] = str(registry)
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "verify_approvals.py")],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )


def test_the_cli_reports_unresolved_claims_as_a_failure_not_a_note(cli_repo: Path) -> None:
    result = _run_cli(cli_repo, cli_repo / "absent.jsonl")
    assert result.returncode == 1, result.stdout
    assert "unresolved approval claim" in result.stdout
    assert "registry unavailable" in result.stdout


def test_the_cli_passes_when_every_key_resolves(cli_repo: Path) -> None:
    registry = _write_registry(cli_repo, _entry())
    result = _run_cli(cli_repo, registry)
    assert result.returncode == 0, result.stdout
    assert "resolves to a registry entry" in result.stdout


@pytest.mark.parametrize("case", ["clean", "unresolved", "nothing-declared"])
def test_every_cli_outcome_states_the_limit_of_what_it_proves(cli_repo: Path, case: str) -> None:
    """The honest-limits rule, applied to the output a human actually reads.

    A green line here is the single most likely thing to be misread as
    "approvals are authentic". It is not: it says the bookkeeping agrees with
    itself. The pass path matters MORE than the failure path, because nobody
    goes looking for the enforcement point after being told everything is fine.

    Injection run 2026-08-12: with `_LIMIT_NOTICE` printed only on the failure
    path (the shape this started as), the `clean` and `nothing-declared` rows
    went red and the `unresolved` row stayed green — which is exactly the
    asymmetry that makes a reassuring pass dangerous. Reverted.
    """
    if case == "clean":
        registry = _write_registry(cli_repo, _entry())
    elif case == "unresolved":
        registry = cli_repo / "absent.jsonl"
    else:
        (cli_repo / "doc" / "specs" / "SPEC-probe.md").write_text(
            "# SPEC: probe\n\nStatus: Draft\nUpstream: none\n", encoding="utf-8"
        )
        subprocess.run(["git", "add", "-A"], cwd=cli_repo, check=True)
        registry = cli_repo / "absent.jsonl"

    result = _run_cli(cli_repo, registry)

    assert "LIMIT (stated limit)" in result.stdout, result.stdout
    assert "EVIDENT, not impossible" in result.stdout
    assert "CI check on a protected branch" in result.stdout


def test_the_cli_says_so_when_nothing_declares_a_key(cli_repo: Path) -> None:
    (cli_repo / "doc" / "specs" / "SPEC-probe.md").write_text(
        "# SPEC: probe\n\nStatus: Draft\nUpstream: none\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=cli_repo, check=True)
    result = _run_cli(cli_repo, cli_repo / "absent.jsonl")
    assert result.returncode == 0, result.stdout
    assert "0 documents declare" in result.stdout


def test_templates_and_framework_docs_are_never_scanned(cli_repo: Path) -> None:
    """`doc/templates/` carries placeholder `Approval:`-shaped lines by design,
    and `doc/framework/` documents the mechanism using literal examples. If the
    verifier scanned them, a fresh clone would fail its own gate on day one."""
    templates = cli_repo / "doc" / "templates"
    templates.mkdir()
    (templates / "spec.md").write_text(
        "# SPEC template\n\nStatus: Approved\nApproval: <registry key>\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=cli_repo, check=True)
    registry = _write_registry(cli_repo, _entry())
    result = _run_cli(cli_repo, registry)
    assert result.returncode == 0, result.stdout
    assert "<registry key>" not in result.stdout


# ---------------------------------------------------------------------------
# The pre-registry exemption: empty here, and the mechanism still has teeth.
# ---------------------------------------------------------------------------


def test_the_template_ships_with_an_empty_pre_registry_cohort() -> None:
    """A project that starts from this template has no history predating its
    registry, so any entry in this set would be an exemption with no reason.
    The set exists for teams migrating an existing repo — and if you populate
    it, pin its size the way this test pins zero."""
    assert verifier._PRE_REGISTRY_ARTIFACTS == frozenset()


def test_a_grandfathered_document_needs_no_registry_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mechanism a migrating team would rely on: listed artifact, no
    registry, no problem."""
    listed = "doc/specs/SPEC-historical.md"
    monkeypatch.setattr(verifier, "_PRE_REGISTRY_ARTIFACTS", frozenset({listed}))
    monkeypatch.setattr(
        verifier, "declared_approvals", lambda: [(listed, "some-old-key", "Approved")]
    )
    monkeypatch.setenv(_REGISTRY_ENV, str(tmp_path / "absent.jsonl"))
    problems, checked, _ = verifier.verify()
    assert (problems, checked) == ([], 1)


def test_a_document_outside_the_cohort_still_needs_a_registry_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The teeth. If this passed with the exemption in place, the cohort would
    be a blanket amnesty and every future approval could skip the registry."""
    listed = "doc/specs/SPEC-historical.md"
    monkeypatch.setattr(verifier, "_PRE_REGISTRY_ARTIFACTS", frozenset({listed}))
    monkeypatch.setattr(
        verifier,
        "declared_approvals",
        lambda: [
            (listed, "some-old-key", "Approved"),
            ("doc/specs/SPEC-brand-new.md", "brand-new-key", "Approved"),
        ],
    )
    monkeypatch.setenv(_REGISTRY_ENV, str(tmp_path / "absent.jsonl"))
    problems, checked, _ = verifier.verify()
    assert checked == 2
    assert [p.artifact for p in problems] == ["doc/specs/SPEC-brand-new.md"]
