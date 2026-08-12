#!/usr/bin/env python3
"""Station tracker for the Scar Forge (NORTH-STAR mechanism ๑, `doc/templates/SCAR.md`).

WHY THIS EXISTS. NORTH-STAR states the pipeline as six fixed stations —
incident, lesson, rule, mechanism, proof, closed gate — and then makes a
specific, falsifiable claim about how to know the forge is working:

    "ตัววัดความสำเร็จไม่ใช่จำนวนกลไกที่มี แต่คือเวลาเฉลี่ยจากแผลถึงกลไก"
    (the measure of success is not how many mechanisms exist, but the AVERAGE
    TIME FROM WOUND TO MECHANISM)

A lesson record sitting in a file answers nothing about that number, or about
"which lessons are stuck at which station, and for how long" (also named
explicitly), unless something reads every record and computes it — without a
human having to remember to go check. This script is that something. It is a
plain, dependency-free, stdlib-only script — no AI agent is required to run
it, per RUNTIME-CONTRACT layer ๑ (แก่นไร้ผู้ปฏิบัติ).

**What this script does NOT do (stated, not glossed):**

* It does not gate on staleness. No wave has yet measured a real incident
  caused by a scar sitting at one station for N days, so there is no number
  to enforce — inventing one would violate the framework's own rule that a
  rule with no scar behind it has no right to exist (คำมั่นของผู้สร้าง ๑). It
  only reports; the human decides what "too long" means for their team.
* It DOES treat two things as mechanically-checkable violations, not mere
  staleness, and exits 1 when it finds either: (a) `Status: Closed` on a scar
  whose Station 6 has no real date — a closed gate with no trace is exactly
  the "โฆษณาเกินความสามารถ" NORTH-STAR calls worse than not having the gate at
  all; (b) a later station entered before an earlier one — the six stations
  are a pipeline, not a checklist to fill in any order.

Usage:
    python3 scripts/scar_status.py
    SCAR_DIR=/tmp/probe python3 scripts/scar_status.py
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCAR_DIR_ENV = "SCAR_DIR"

#: Deliberately NOT the handoff-protocol vocabulary (`Draft|In Review|
#: Approved|Done|Living`) — see `doc/templates/SCAR.md` for why a scar uses
#: its own three words instead of piggybacking on the approval-gated one.
_VALID_STATUSES = ("Open", "In Forge", "Closed")
_CLOSED_STATUS = "Closed"

_STATION_NAMES = {
    1: "เหตุการณ์ที่พลาด (Incident)",
    2: "บทเรียน (Lesson)",
    3: "กฎ (Rule)",
    4: "กลไก (Mechanism)",
    5: "พิสูจน์ (Proof it bites)",
    6: "ด่านปิด (Closed gate)",
}
_MECHANISM_STATION = 4
_INCIDENT_STATION = 1
_CLOSED_STATION = 6

_TITLE_RE = re.compile(r"^#\s*SCAR:\s*(.+?)\s*$", re.MULTILINE)
_STATUS_RE = re.compile(r"^Status:\s*(.+?)\s*$", re.MULTILINE)
_STATION_BLOCK_RE = re.compile(
    r"^##\s*Station\s+(\d)\s*—.*?$(.*?)(?=^##\s*Station\s+\d|\Z)",
    re.MULTILINE | re.DOTALL,
)
_ENTERED_RE = re.compile(r"^Entered:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
_OWNER_RE = re.compile(r"^Owner:\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Scar:
    """One parsed scar record."""

    path: Path
    title: str
    status: str | None
    stations: dict[int, date] = field(default_factory=dict)  # station number -> Entered date
    owners: dict[int, str] = field(default_factory=dict)  # station number -> Owner

    def current_station(self) -> int | None:
        """The highest-numbered station with a real `Entered:` date, or None
        if the scar has not even reached Station 1 yet."""
        if not self.stations:
            return None
        return max(self.stations)


@dataclass(frozen=True)
class Problem:
    """A mechanically-detected inconsistency between a scar's `Status:` line
    and its stations — not staleness, which this script never treats as an
    error."""

    path: Path
    reason: str


def scar_dir() -> Path:
    override = os.environ.get(_SCAR_DIR_ENV)
    return Path(override).expanduser() if override else _REPO_ROOT / "doc" / "scars"


def parse_scar(path: Path) -> Scar:
    """Parse one scar file. Missing fields become `None`/empty — a scar with
    no stations yet is a valid (if very early) scar, not a parse error."""
    text = path.read_text(encoding="utf-8")
    title_match = _TITLE_RE.search(text)
    status_match = _STATUS_RE.search(text)
    title = title_match.group(1) if title_match else path.stem
    status = status_match.group(1) if status_match else None

    stations: dict[int, date] = {}
    owners: dict[int, str] = {}
    for number_str, body in _STATION_BLOCK_RE.findall(text):
        number = int(number_str)
        entered_match = _ENTERED_RE.search(body)
        if entered_match:
            y, m, d = (int(part) for part in entered_match.group(1).split("-"))
            stations[number] = date(y, m, d)
        # An owner is recorded even for a station not yet entered — NORTH-STAR
        # requires every station to have one, and "who is supposed to be
        # working on this" is exactly what a human asks about a stuck scar.
        owner_match = _OWNER_RE.search(body)
        if owner_match and not owner_match.group(1).startswith("<"):
            owners[number] = owner_match.group(1)
    return Scar(path=path, title=title, status=status, stations=stations, owners=owners)


def load_all(directory: Path) -> list[Scar]:
    """Every `.md` file directly under `directory`, sorted for deterministic
    output. Not recursive — scars are flat, one file per record."""
    if not directory.is_dir():
        return []
    return [parse_scar(p) for p in sorted(directory.glob("*.md"))]


def find_problems(scars: list[Scar]) -> list[Problem]:
    problems: list[Problem] = []
    for scar in scars:
        if scar.status is not None and scar.status not in _VALID_STATUSES:
            problems.append(
                Problem(
                    scar.path,
                    f"Status: {scar.status!r} is not one of {_VALID_STATUSES} — a scar "
                    f"deliberately does not use 'Approved'/'Done' (see doc/templates/SCAR.md), "
                    f"because the CI approval-registry gate would then demand an Approval: "
                    f"key this document was never meant to carry",
                )
            )
        if scar.status == _CLOSED_STATUS and _CLOSED_STATION not in scar.stations:
            problems.append(
                Problem(
                    scar.path,
                    f"Status: {_CLOSED_STATUS} but Station {_CLOSED_STATION} "
                    f"({_STATION_NAMES[_CLOSED_STATION]}) has no `Entered:` date — "
                    f"a closed gate with no trace is not closed",
                )
            )
        reached = sorted(scar.stations)
        expected = list(range(1, len(reached) + 1))
        if reached != expected:
            problems.append(
                Problem(
                    scar.path,
                    f"stations entered out of order: {reached} (expected a prefix of 1..6, "
                    f"e.g. {expected})",
                )
            )
    return problems


def scar_to_mechanism_days(scar: Scar) -> int | None:
    """Days from Station 1 (incident) to Station 4 (mechanism) — the exact
    number NORTH-STAR names as the forge's success metric. None if either
    end is not yet reached."""
    start = scar.stations.get(_INCIDENT_STATION)
    end = scar.stations.get(_MECHANISM_STATION)
    if start is None or end is None:
        return None
    return (end - start).days


def render_report(scars: list[Scar], today: date, directory: Path) -> tuple[str, list[Problem]]:
    lines: list[str] = []
    lines.append(f"scar forge status — {directory} ({len(scars)} record(s))")

    if not scars:
        lines.append("  no scar records yet — nothing to report.")
        return "\n".join(lines), []

    problems = find_problems(scars)

    open_scars = [s for s in scars if s.status != _CLOSED_STATUS]
    lines.append("")
    lines.append(f"open ({len(open_scars)}) — stuck at which station, and for how long:")
    if not open_scars:
        lines.append("  none — every recorded scar is Closed.")
    else:
        rows = []
        for scar in open_scars:
            current = scar.current_station()
            if current is None:
                rows.append((10**9, scar, None, "not yet at Station 1"))
                continue
            entered = scar.stations[current]
            stuck_days = (today - entered).days
            owner = scar.owners.get(current, "(no owner recorded)")
            rows.append(
                (
                    stuck_days,
                    scar,
                    current,
                    f"Station {current} ({_STATION_NAMES[current]}), "
                    f"entered {entered.isoformat()}, stuck {stuck_days}d, owner: {owner}",
                )
            )
        rows.sort(key=lambda row: row[0], reverse=True)
        for _, scar, _current, description in rows:
            lines.append(f"  {scar.path.name}: {description}")

    deltas = [d for d in (scar_to_mechanism_days(s) for s in scars) if d is not None]
    lines.append("")
    lines.append("scar-to-mechanism latency (Station 1 -> Station 4), the NORTH-STAR metric:")
    if not deltas:
        lines.append("  0 record(s) have both dates — nothing to average yet.")
    else:
        lines.append(f"  {len(deltas)} record(s): {deltas} days")
        lines.append(f"  average: {sum(deltas) / len(deltas):.1f} days")

    if problems:
        lines.append("")
        lines.append(f"{len(problems)} inconsistency/ies (not staleness — a broken claim):")
        for problem in problems:
            lines.append(f"  {problem.path.name}: {problem.reason}")

    lines.append("")
    lines.append(
        "LIMIT (stated limit): this reports staleness, it never gates on it — no measured "
        "incident yet backs a specific day threshold, and a threshold with no scar behind it "
        "has no right to exist. It DOES fail (exit 1) when it finds a Closed scar with no "
        "Station 6 date, or stations entered out of order — those are checkable claims about "
        "this file, not judgement calls about how long is too long."
    )
    return "\n".join(lines), problems


def main() -> int:
    directory = scar_dir()
    scars = load_all(directory)
    report, problems = render_report(scars, date.today(), directory)
    print(report)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
