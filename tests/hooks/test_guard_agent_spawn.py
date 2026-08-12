"""`guard_agent_spawn.py` — the gate on spawning implementer agents.

Two properties matter roughly equally here, and the second is the one that
gets guards deleted:

* the gate blocks an implementer spawn whose upstream document is not
  `Approved`;
* the gate does **not** block anything else — not `qa`, not `ba-sa`, not
  `Explore`, and not a legitimate no-spec bugfix that states its basis.

Every scenario is built from temporary probe documents written into
`doc/specs/` / `doc/architecture/` and removed afterwards, so these tests
neither depend on nor are invalidated by the actual approval state of the
repo. On the originating project, the first hook suite skipped eight
assertions whenever the tree happened to be clean — the state CI always checks
out — so ambient state is never trusted here.

Run: `python3 -m pytest tests/hooks/ -q`   (no project dependencies required)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SPAWN_GATE = _REPO_ROOT / ".claude" / "hooks" / "guard_agent_spawn.py"

_EXIT_ALLOW = 0
_EXIT_BLOCK = 2

_GATED = ("ai-engineer", "frontend-engineer")
_UNGATED = ("qa", "ba-sa", "pm", "Explore", "Plan", "general-purpose", "frontend-qa")

# Probe names that cannot collide with real documents.
_PROBE_SPEC = "SPEC-zz99-agent-gate-probe.md"
_PROBE_DESIGN = "DESIGN-zz99-agent-gate-probe.md"


def _run_gate(
    *, subagent_type: str, prompt: str, tool_name: str = "Agent"
) -> subprocess.CompletedProcess[str]:
    payload = json.dumps(
        {
            "tool_name": tool_name,
            "tool_input": {"subagent_type": subagent_type, "prompt": prompt},
        }
    )
    return subprocess.run(
        [sys.executable, str(_SPAWN_GATE)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


@pytest.fixture
def probe_doc():
    """Writes a temporary document with a chosen Status into the repo, then
    removes it. The gate resolves documents by repo path, so the file has to
    live there — but it must never survive the test."""
    created: list[Path] = []

    def _write(status_line: str | None, *, directory: str = "doc/specs", name: str = _PROBE_SPEC):
        path = _REPO_ROOT / directory / name
        body = "# Probe document for the agent-spawn gate test\n\n"
        if status_line is not None:
            body += f"{status_line}\n"
        body += "\nUpstream: `tests/hooks/test_guard_agent_spawn.py`\n"
        path.write_text(body, encoding="utf-8")
        created.append(path)
        return name

    yield _write

    for path in created:
        if path.exists():
            path.unlink()
    for leftover in (_REPO_ROOT / "doc" / "specs" / _PROBE_SPEC,
                     _REPO_ROOT / "doc" / "architecture" / _PROBE_DESIGN):
        assert not leftover.exists(), f"probe document leaked: {leftover}"


# ---------------------------------------------------------------------------
# The gate reads the Status line.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("subagent_type", _GATED)
def test_an_approved_spec_allows_the_spawn(subagent_type: str, probe_doc) -> None:
    name = probe_doc("Status: Approved")
    result = _run_gate(
        subagent_type=subagent_type,
        prompt=f"Implement doc/specs/{name} exactly as written.",
    )
    assert result.returncode == _EXIT_ALLOW, result.stderr


@pytest.mark.parametrize("status", ["Draft", "In Review", "Done", "Living"])
def test_a_non_approved_spec_blocks_the_spawn_and_names_the_status(status: str, probe_doc) -> None:
    """The message must name the document *and* its actual status — a bare
    "blocked" tells the reader nothing about what to fix.

    Injection run 2026-08-12: with the status comparison loosened to accept
    any non-empty status (`status != _ALLOWED_STATUS` replaced by
    `not status`), six tests went red — all four rows of this matrix, plus the
    two other tests that rely on a Draft probe blocking — meaning every
    unapproved document then authorised an implementer. The ungated-types and
    override tests stayed green. Reverted."""
    name = probe_doc(f"Status: {status}")
    result = _run_gate(subagent_type="ai-engineer", prompt=f"Implement doc/specs/{name}.")
    assert result.returncode == _EXIT_BLOCK, result.stdout
    assert name in result.stderr
    assert status in result.stderr


def test_a_spec_with_no_status_line_blocks(probe_doc) -> None:
    name = probe_doc(None)
    result = _run_gate(subagent_type="ai-engineer", prompt=f"Implement doc/specs/{name}.")
    assert result.returncode == _EXIT_BLOCK
    assert "no `Status:` line" in result.stderr


def test_a_named_spec_that_does_not_exist_blocks_rather_than_passing() -> None:
    """A typo in a spec name must not read as "no spec named, so fall through"."""
    result = _run_gate(
        subagent_type="ai-engineer",
        prompt="Implement doc/specs/SPEC-zz98-does-not-exist.md.",
    )
    assert result.returncode == _EXIT_BLOCK
    assert "file not found" in result.stderr


def test_a_decorated_approved_status_is_still_read_as_approved(probe_doc) -> None:
    """A repo migrating onto this framework carries decorated lines like
    `Status: Approved (human-approved 2026-07-20)`. The gate reads the leading
    word, so migration does not block every spawn — policing the grammar
    itself is the document-contract check's job, not this gate's."""
    name = probe_doc("Status: Approved (human-approved 2026-07-20)")
    result = _run_gate(subagent_type="ai-engineer", prompt=f"Implement doc/specs/{name}.")
    assert result.returncode == _EXIT_ALLOW, result.stderr


def test_one_approved_spec_among_several_references_is_enough(probe_doc) -> None:
    """A prompt often quotes a superseded spec or a design doc for context.
    Blocking on those would be a false positive, and false positives get
    guards switched off."""
    name = probe_doc("Status: Approved")
    result = _run_gate(
        subagent_type="ai-engineer",
        prompt=(
            f"Implement doc/specs/{name}. For context see "
            f"doc/specs/SPEC-zz97-superseded.md which no longer exists."
        ),
    )
    assert result.returncode == _EXIT_ALLOW, result.stderr


# ---------------------------------------------------------------------------
# DESIGN documents are upstreams too — in their own directory.
# ---------------------------------------------------------------------------


class TestDesignDocumentsCountAsUpstream:
    """On the originating project a DESIGN document could not be named as an
    upstream at all: the reference pattern did not accept the prefix, and the
    resolver hardcoded `doc/specs/` — so every legitimately approved design
    forced the override token instead. A gate people are trained to bypass is
    worse than no gate, because it also carries the appearance of control."""

    def test_an_approved_design_document_is_accepted_by_repo_path(self, probe_doc) -> None:
        name = probe_doc(
            "Status: Approved", directory="doc/architecture", name=_PROBE_DESIGN
        )
        result = _run_gate(
            subagent_type="ai-engineer",
            prompt=f"Implement doc/architecture/{name}.",
        )
        assert result.returncode == _EXIT_ALLOW, result.stderr

    def test_an_approved_design_document_is_accepted_by_bare_filename(self, probe_doc) -> None:
        name = probe_doc(
            "Status: Approved", directory="doc/architecture", name=_PROBE_DESIGN
        )
        result = _run_gate(subagent_type="ai-engineer", prompt=f"Implement {name}.")
        assert result.returncode == _EXIT_ALLOW, result.stderr

    def test_a_design_document_that_does_not_exist_is_still_blocked(self) -> None:
        """Accepting the prefix must not become accepting the claim: the file
        still has to be there and still has to be Approved."""
        result = _run_gate(
            subagent_type="ai-engineer", prompt="Implement DESIGN-zz98-does-not-exist.md."
        )
        assert result.returncode == _EXIT_BLOCK, result.stdout

    def test_a_design_document_is_resolved_in_its_own_directory(self, probe_doc) -> None:
        """The second half of the original defect: a DESIGN file lives in
        `doc/architecture/`, and looking it up under `doc/specs/` reports
        `file not found` for a document sitting right there."""
        name = probe_doc(
            "Status: Draft", directory="doc/architecture", name=_PROBE_DESIGN
        )
        result = _run_gate(subagent_type="ai-engineer", prompt=f"Implement {name}.")
        # Draft blocks — but the reason must be its status, not a wrong path.
        assert result.returncode == _EXIT_BLOCK
        assert "Draft" in result.stderr
        assert "file not found" not in result.stderr


# ---------------------------------------------------------------------------
# Fail-closed, with a stated override.
# ---------------------------------------------------------------------------


def test_no_spec_named_blocks_and_explains_both_remedies() -> None:
    result = _run_gate(subagent_type="ai-engineer", prompt="Just fix the thing please.")
    assert result.returncode == _EXIT_BLOCK
    assert "NO_SPEC_BUGFIX:" in result.stderr
    assert "name the spec" in result.stderr


def test_the_override_with_a_reproduction_allows_the_spawn() -> None:
    """CLAUDE.md §5 permits a small bugfix with a clear reproduction to start
    at the engineer — the section that actually carries the rule. The hook's
    own message cited §6 (the approval gates) until 2026-08-12; a guard that
    misdirects the reader to the wrong rule teaches the wrong rule."""
    result = _run_gate(
        subagent_type="ai-engineer",
        prompt=(
            "NO_SPEC_BUGFIX: submitting the form with a trailing space in the "
            "amount field crashes the parser with ValueError."
        ),
    )
    assert result.returncode == _EXIT_ALLOW, result.stderr


def test_a_bare_override_token_with_no_reason_is_still_blocked() -> None:
    """An override that needs no justification is a rubber stamp.

    Injection run 2026-08-12: with `_MIN_OVERRIDE_REASON_CHARS` dropped to 0,
    this test alone went red — `NO_SPEC_BUGFIX: x` then authorised a spawn on a
    one-character basis — while the with-reproduction test above stayed green.
    Reverted."""
    result = _run_gate(subagent_type="ai-engineer", prompt="NO_SPEC_BUGFIX: x")
    assert result.returncode == _EXIT_BLOCK
    assert "carries no reproduction" in result.stderr


def test_the_gate_refuses_to_suggest_editing_the_status_line(probe_doc) -> None:
    """The one remedy that must never be offered: an agent writing its own
    approval is precisely what the registry deny hook exists to prevent."""
    name = probe_doc("Status: Draft")
    result = _run_gate(subagent_type="ai-engineer", prompt=f"Implement doc/specs/{name}.")
    assert result.returncode == _EXIT_BLOCK
    assert "do NOT edit" in result.stderr


# ---------------------------------------------------------------------------
# Everything else passes through.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("subagent_type", _UNGATED)
def test_ungated_agent_types_are_never_blocked(subagent_type: str) -> None:
    """Gating investigation agents would block ordinary work, and a guard with
    false positives gets disabled."""
    result = _run_gate(
        subagent_type=subagent_type,
        prompt="Investigate why the score dropped. No spec named on purpose.",
    )
    assert result.returncode == _EXIT_ALLOW, result.stderr


def test_a_non_agent_tool_call_passes_through() -> None:
    result = _run_gate(subagent_type="ai-engineer", prompt="no spec", tool_name="Bash")
    assert result.returncode == _EXIT_ALLOW


def test_a_malformed_payload_fails_open_rather_than_wedging_every_spawn() -> None:
    """A hook bug must not make the pipeline unusable."""
    result = subprocess.run(
        [sys.executable, str(_SPAWN_GATE)],
        input="not json",
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == _EXIT_ALLOW


def test_the_gate_is_registered_in_settings_json() -> None:
    """A hook file that is not wired in never runs — the quietest possible
    failure."""
    settings = json.loads((_REPO_ROOT / ".claude" / "settings.json").read_text())
    assert "guard_agent_spawn.py" in json.dumps(settings)
    matchers = [
        entry.get("matcher", "")
        for entry in settings["hooks"]["PreToolUse"]
        if "guard_agent_spawn.py" in json.dumps(entry)
    ]
    assert matchers, "no PreToolUse entry registers the spawn gate"
    assert any("Agent" in matcher for matcher in matchers), (
        f"the spawn gate is registered but not on the Agent tool: {matchers}"
    )
