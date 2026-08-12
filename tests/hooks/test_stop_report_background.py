"""`stop_report_background.py` — the Stop reporter, and the detection test it
never had.

The first version of this hook buried its matching inside `main()`, and its
only test proved the hook *cannot block* (exit 0 whatever happens). Nothing
proved it *detects* — which for a reporting hook is the whole job, and a
reporter that detects nothing is indistinguishable from one that works, right
up until a forgotten harness produces a wrong measurement again. The matcher
is now a pure function, `matching_lines`, tested here against constructed
`ps` output so nothing depends on what happens to be running on this machine.

Run: `python3 -m pytest tests/hooks/ -q`   (no project dependencies required)
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOK_PATH = _REPO_ROOT / ".claude" / "hooks" / "stop_report_background.py"

_EXIT_ALLOW = 0


def _load_hook():
    spec = importlib.util.spec_from_file_location("framework_stop_report", _HOOK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


hook = _load_hook()

_HEADER = "  PID     ELAPSED COMMAND"


def test_a_matching_process_is_detected() -> None:
    """The half the original suite never held.

    Injection run 2026-08-12: with `matching_lines` returning `[]`
    unconditionally — the shape of a reporter that silently rots — this test
    alone went red. Every other test stayed green, including the exit-code
    test that was the original suite's ONLY coverage: a fully dead detector
    still exits 0 politely, which is exactly the blind spot this test closes.
    Reverted."""
    ps = f"{_HEADER}\n  123   01:02:03 python3 -m pytest tests/ -q\n"
    hits = hook.matching_lines(ps)
    assert len(hits) == 1
    assert "pytest" in hits[0]


def test_a_non_matching_process_is_not_reported() -> None:
    ps = f"{_HEADER}\n  124   00:00:01 /usr/libexec/thing --daemon\n"
    assert hook.matching_lines(ps) == []


def test_the_hook_does_not_report_itself() -> None:
    """Without the self-exclusion every stop would report the reporter, and a
    notice that always fires is a notice nobody reads."""
    ps = (
        f"{_HEADER}\n"
        f"  125   00:00:01 python3 .claude/hooks/stop_report_background.py\n"
        f"  126   00:00:02 ps -eo pid,etime,command\n"
    )
    assert hook.matching_lines(ps) == []


def test_the_header_row_is_dropped_even_if_it_would_match() -> None:
    """`matching_lines` receives raw `ps` output, header included. The header
    is positional (first line), not textual — a COMMAND column heading that
    happened to contain a pattern must not become a phantom process."""
    ps = "PID ETIME COMMAND (pytest node )\n"
    assert hook.matching_lines(ps) == []


def test_condense_keeps_the_identifying_head_and_tail() -> None:
    """Measured on the originating machine: a virtualenv Python resolves
    through ~130 characters of interpreter path before the script name is even
    reached, so truncating from one end alone throws away the only part that
    identifies which process to kill."""
    head = "  123   01:02:03 /very/long/interpreter/path/"
    tail = "scripts/my_actual_harness.py --flag value"
    line = head + ("x" * 300) + " " + tail
    condensed = hook.condense(line)
    assert len(condensed) <= 200 + len(" … ")
    assert condensed.startswith(head[:40])
    assert condensed.endswith(tail[-40:])
    assert "my_actual_harness.py" in condensed


def test_a_short_line_is_left_alone() -> None:
    line = "  123   01:02:03 pytest -q"
    assert hook.condense(line) == line


def test_the_hook_reports_without_ever_blocking() -> None:
    """Rule A4 is advisory: it must exit 0 whatever it finds — a Stop hook
    that blocked would strand the turn."""
    result = subprocess.run(
        [sys.executable, str(_HOOK_PATH)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == _EXIT_ALLOW
    if result.stderr.strip():
        assert "Live background processes" in result.stderr


def test_the_hook_is_registered_on_stop_in_settings_json() -> None:
    """A hook file that is not wired into settings.json never runs."""
    settings = json.loads((_REPO_ROOT / ".claude" / "settings.json").read_text())
    stop_entries = json.dumps(settings["hooks"].get("Stop", []))
    assert "stop_report_background.py" in stop_entries
