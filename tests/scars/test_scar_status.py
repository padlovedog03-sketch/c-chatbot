"""Tests for `scripts/scar_status.py` — the Scar Forge's station tracker.

WHY THIS FILE EXISTS. NORTH-STAR names a specific, falsifiable number as the
forge's actual success metric ("เวลาเฉลี่ยจากแผลถึงกลไก" — average time from
wound to mechanism) and a specific question a human should never have to
remember to ask ("which lessons are stuck at which station, and for how
long"). A parser that mis-reads a station date, or a script that silently
swallows a broken `Status: Closed` claim, would make both of those false
without ever printing an error — exactly the silent-failure shape this whole
repo exists to refuse. So both directions are pinned here: the happy path
(parsing this repo's own real worked example, `doc/scars/
SCAR-exit-gate-green-lie.md`) AND the two mechanically-detected violations,
proven by real injection the same way `tests/hooks/` proves its guards bite.

Run: `python3 -m pytest tests/scars/ -q`   (no project dependencies required)
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "scar_status.py"

sys.path.insert(0, str(_REPO_ROOT / "scripts"))
import scar_status as ss  # noqa: E402  (path must be set up first)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _station(number: int, name: str, entered: str, owner: str = "someone", body: str = "") -> str:
    """One `## Station N` block, in the exact shape `doc/templates/SCAR.md` uses."""
    return f"## Station {number} — {name}\n\nEntered: {entered}\nOwner: {owner}\n\n{body}\n\n"


def _scar(title: str, status: str, stations: str) -> str:
    return f"# SCAR: {title}\n\nStatus: {status}\nUpstream: test\nOpened: 2026-01-01\n\n{stations}"


# ---------------------------------------------------------------------------
# The real worked example — the happy path, on real material
# ---------------------------------------------------------------------------


def test_parses_the_real_worked_example() -> None:
    path = _REPO_ROOT / "doc" / "scars" / "SCAR-exit-gate-green-lie.md"
    assert path.is_file(), "the Task B worked example is missing"

    scar = ss.parse_scar(path)

    assert scar.status == "Closed"
    assert scar.stations.keys() == {1, 2, 3, 4, 5, 6}, scar.stations
    assert scar.current_station() == 6
    assert ss.scar_to_mechanism_days(scar) == 0  # same-day incident-to-mechanism, measured
    assert ss.find_problems([scar]) == []


def test_the_worked_example_directory_reports_clean_via_the_real_cli() -> None:
    """The actual command a human or a cron job would run, executed for real
    against this repo's real `doc/scars/` — not a fixture standing in for it."""
    result = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SCAR-exit-gate-green-lie.md" not in result.stdout.split("open (0)")[0]
    assert "average: 0.0 days" in result.stdout


# ---------------------------------------------------------------------------
# Parsing edge cases: an unfilled station must never be mistaken for reached
# ---------------------------------------------------------------------------


def test_a_literal_yyyy_mm_dd_placeholder_is_not_a_reached_station(tmp_path: Path) -> None:
    body = _station(1, "เหตุการณ์ที่พลาด (Incident)", "2026-02-01") + _station(
        2, "บทเรียน (Lesson)", "YYYY-MM-DD", owner="<who>"
    )
    path = _write(tmp_path / "SCAR-edge.md", _scar("edge", "Open", body))

    scar = ss.parse_scar(path)

    assert scar.stations == {1: date(2026, 2, 1)}
    assert scar.current_station() == 1


def test_current_station_is_the_highest_one_actually_reached(tmp_path: Path) -> None:
    body = "".join(
        _station(n, f"station {n}", f"2026-03-{n:02d}") for n in (1, 2, 3)
    ) + _station(4, "station 4", "YYYY-MM-DD", owner="<who>")
    path = _write(tmp_path / "SCAR-partial.md", _scar("partial", "In Forge", body))

    scar = ss.parse_scar(path)

    assert scar.current_station() == 3


def test_a_scar_with_zero_stations_reached_reports_none() -> None:
    scar = ss.Scar(path=Path("x"), title="x", status="Open", stations={})
    assert scar.current_station() is None


# ---------------------------------------------------------------------------
# The NORTH-STAR metric: Station 1 -> Station 4
# ---------------------------------------------------------------------------


def test_scar_to_mechanism_days_is_none_when_station_4_not_reached() -> None:
    scar = ss.Scar(path=Path("x"), title="x", status="Open", stations={1: date(2026, 1, 1)})
    assert ss.scar_to_mechanism_days(scar) is None


def test_scar_to_mechanism_days_counts_the_real_gap() -> None:
    scar = ss.Scar(
        path=Path("x"),
        title="x",
        status="Closed",
        stations={1: date(2026, 1, 1), 4: date(2026, 1, 5)},
    )
    assert ss.scar_to_mechanism_days(scar) == 4


def test_average_latency_is_computed_across_multiple_scars(tmp_path: Path) -> None:
    # `status="In Forge"` deliberately, and Stations 1-4 filled in order (the
    # pipeline requires 2 and 3 before 4 exists at all): these are still
    # open, so neither of `render_report`'s validity checks (Closed-with-no-
    # Station-6, out-of-order stations) should fire — this test is about the
    # arithmetic, not about scar validity.
    fast = ss.Scar(
        path=Path("fast"), title="fast", status="In Forge",
        stations={
            1: date(2026, 1, 1), 2: date(2026, 1, 1),
            3: date(2026, 1, 2), 4: date(2026, 1, 3),
        },
    )
    slow = ss.Scar(
        path=Path("slow"), title="slow", status="In Forge",
        stations={
            1: date(2026, 1, 1), 2: date(2026, 1, 3),
            3: date(2026, 1, 5), 4: date(2026, 1, 7),
        },
    )
    report, problems = ss.render_report([fast, slow], date(2026, 1, 10), tmp_path)

    assert problems == [], problems
    assert "[2, 6] days" in report
    assert "average: 4.0 days" in report


# ---------------------------------------------------------------------------
# The two mechanically-checked violations — proven by real injection, run
# through the actual CLI (`python3 scripts/scar_status.py`), matching the
# bite-proof standard `tests/hooks/` already holds every guard to.
# ---------------------------------------------------------------------------


def _run_cli(scar_dir: Path) -> subprocess.CompletedProcess[str]:
    import os

    env = {**os.environ, "SCAR_DIR": str(scar_dir)}
    return subprocess.run(
        [sys.executable, str(_SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_closed_with_no_station_6_date_goes_red_naming_the_file(tmp_path: Path) -> None:
    """Injection: a forged scar claims `Status: Closed` while Station 6 is
    still an unfilled placeholder — a closed gate with no trace.

    Measured: `python3 scripts/scar_status.py` against a directory containing
    only this file exits 1 and names the file and the missing station.

    Injection run 2026-08-12: with the Closed-with-no-Station-6 check removed
    from `find_problems`, this test alone went red — `returncode` came back
    `0` and the forged scar was reported as a normal Closed record, no
    mention of the missing trace. Reverted; `diff` against the pre-injection
    copy was empty.
    """
    body = "".join(_station(n, f"station {n}", f"2026-04-{n:02d}") for n in (1, 2, 3, 4, 5))
    body += _station(6, "ด่านปิด (Closed gate)", "YYYY-MM-DD", owner="<who>")
    scar_dir = tmp_path / "scars"
    _write(scar_dir / "SCAR-forged-closed.md", _scar("forged closed", "Closed", body))

    result = _run_cli(scar_dir)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "SCAR-forged-closed.md" in result.stdout
    assert "Station 6" in result.stdout
    assert "no trace" in result.stdout.lower() or "no `Entered:` date" in result.stdout


def test_closed_with_a_real_station_6_date_passes(tmp_path: Path) -> None:
    """The complement: a genuinely closed scar (all six stations dated) must
    NOT be flagged — otherwise the check above would be indistinguishable
    from a check that rejects every closed scar."""
    body = "".join(_station(n, f"station {n}", f"2026-04-{n:02d}") for n in range(1, 7))
    scar_dir = tmp_path / "scars"
    _write(scar_dir / "SCAR-really-closed.md", _scar("really closed", "Closed", body))

    result = _run_cli(scar_dir)

    assert result.returncode == 0, result.stdout + result.stderr


def test_stations_entered_out_of_order_goes_red(tmp_path: Path) -> None:
    """Injection: Station 3 has a real date but Station 2 does not — skipping
    ahead in the pipeline, which the tracker must not silently accept as
    "currently at Station 3".

    Injection run 2026-08-12: with the out-of-order check removed from
    `find_problems`, this test alone went red — the scar was reported as a
    normal open record "stuck at Station 3, 102d", with no indication that
    Station 2 was never actually reached. Reverted; `diff` against the
    pre-injection copy was empty.
    """
    body = _station(1, "station 1", "2026-05-01")
    body += _station(2, "station 2", "YYYY-MM-DD", owner="<who>")
    body += _station(3, "station 3", "2026-05-02")
    scar_dir = tmp_path / "scars"
    _write(scar_dir / "SCAR-out-of-order.md", _scar("out of order", "In Forge", body))

    result = _run_cli(scar_dir)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "SCAR-out-of-order.md" in result.stdout
    assert "out of order" in result.stdout


def test_the_current_stations_owner_is_shown_in_the_report(tmp_path: Path) -> None:
    """NORTH-STAR requires every station to have an owner; the report has to
    surface it, not just parse it and throw it away — "who is stuck on this"
    is exactly what a human reading the report needs next."""
    body = _station(1, "station 1", "2026-06-01", owner="ทีม A")
    scar_dir = tmp_path / "scars"
    _write(scar_dir / "SCAR-owned.md", _scar("owned", "Open", body))

    result = _run_cli(scar_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "owner: ทีม A" in result.stdout


def test_an_unfilled_owner_placeholder_is_not_reported_as_a_real_owner(tmp_path: Path) -> None:
    """The template ships `Owner: <who>` — that literal text must never be
    printed as though a real owner had been recorded."""
    body = _station(1, "station 1", "2026-06-01", owner="<who>")
    scar_dir = tmp_path / "scars"
    _write(scar_dir / "SCAR-unowned.md", _scar("unowned", "Open", body))

    result = _run_cli(scar_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "owner: (no owner recorded)" in result.stdout
    assert "<who>" not in result.stdout


def test_an_invalid_status_value_goes_red(tmp_path: Path) -> None:
    """Injection: a scar accidentally carries `Status: Done` — copied by habit
    from a spec/PRD template. Left unchecked, this would collide with
    `scripts/verify_approvals.py` and the CI registry gate, both of which
    treat `Status: Done` as an approval claim requiring a registry key.

    Injection run 2026-08-12: with this check removed from `find_problems`,
    this test alone went red — `returncode` came back `0` and the malformed
    scar was reported with no warning at all. Reverted; `diff` against the
    pre-injection copy was empty.
    """
    body = _station(1, "station 1", "2026-06-01")
    scar_dir = tmp_path / "scars"
    _write(scar_dir / "SCAR-wrong-vocabulary.md", _scar("wrong vocabulary", "Done", body))

    result = _run_cli(scar_dir)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "SCAR-wrong-vocabulary.md" in result.stdout
    assert "'Done'" in result.stdout


def test_an_empty_or_missing_scar_directory_is_not_an_error(tmp_path: Path) -> None:
    """Day one of a new project: no scars exist yet. That is a fact to report,
    never a crash — the same distinction `verify_approvals.py` draws between
    "nothing to check" and "something is broken"."""
    result = _run_cli(tmp_path / "does-not-exist")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "no scar records yet" in result.stdout


def test_open_scars_are_reported_stuck_first_first(tmp_path: Path) -> None:
    """Sorted so the most-overdue lesson is the first line a human reads, not
    something they have to find by scanning."""
    scar_dir = tmp_path / "scars"
    barely_stuck = _station(1, "station 1", date.today().isoformat())
    long_stuck = _station(1, "station 1", "2020-01-01")
    _write(scar_dir / "SCAR-barely.md", _scar("barely stuck", "Open", barely_stuck))
    _write(scar_dir / "SCAR-long.md", _scar("long stuck", "Open", long_stuck))

    result = _run_cli(scar_dir)

    assert result.returncode == 0, result.stdout + result.stderr
    barely_pos = result.stdout.index("SCAR-barely.md")
    long_pos = result.stdout.index("SCAR-long.md")
    assert long_pos < barely_pos, "the long-stuck scar must be listed before the barely-stuck one"
