#!/usr/bin/env python3
"""Stop hook: surface live background processes owned by this repo.

Rule A4. On the project this framework came from, a background harness that was
believed dead kept running, and the load from its eight concurrent workers was
misread as the cloud provider failing intermittently — a wrong cause, reported to
the human before the real one was found. A process nobody knows is running is also
a live cost, because these harnesses call paid APIs.

Prints a notice on stop when anything matching this repo's harness/server
shapes is still alive. Always exits 0 — this reports, it never blocks.

The matcher is a pure function, ``matching_lines``, so its teeth can be tested
without depending on whatever happens to be running on the machine. The first
version buried the matching inside ``main()``, and its only test proved the hook
*cannot block* — nothing proved it *detects*, which for a reporting hook is the
whole job.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable

# ---------------------------------------------------------------------------
# CONFIGURE THIS for your project.
#
# Command-line fragments worth reporting when a turn ends. The defaults are the
# ones almost every project has; add your dev server, your migration tool, and
# any scratch directory your measurement harnesses run from.
#
# WHY THIS HOOK EXISTS. A background process nobody remembers is running does two
# kinds of harm, and both have happened. It keeps spending whatever the process
# costs — cloud quota, a database connection, a paid API — long after anyone is
# watching. And a forgotten harness has already produced one *wrong measurement*,
# because a second copy of a job was still writing while a result was being read.
# This hook does not stop anything; it just refuses to let a live process leave
# the room silently.
PATTERNS: tuple[str, ...] = (
    "pytest",
    "npm run",
    "node ",
    # "uvicorn",              # your dev server
    # "alembic",              # your migration tool
    # "scratch",              # where measurement harnesses run
)

# Lines that are this hook itself, or the tooling it runs, and would otherwise
# make every stop report a false hit.
SELF_MARKERS: tuple[str, ...] = (
    "stop_report_background",
    "grep ",
    "ps -eo",
)

_MAX_REPORTED = 12

# Line budget, and how it is spent. Measured on the machine this framework came
# from: a virtualenv Python resolves through the interpreter framework to ~130
# characters of path before the script name is even reached. Truncating a line
# from the right alone can therefore throw away the ONLY part that identifies
# which process to kill, which is the entire purpose of this report. Keeping
# both ends and eliding the middle fixes that while still capping the output.
_MAX_LINE_CHARS = 200
_HEAD_CHARS = 80
_ELLIPSIS = " … "
_TAIL_CHARS = _MAX_LINE_CHARS - _HEAD_CHARS - len(_ELLIPSIS)


def condense(line: str) -> str:
    """Shorten an over-long ``ps`` line, keeping the identifying head AND tail."""
    if len(line) <= _MAX_LINE_CHARS:
        return line
    return line[:_HEAD_CHARS] + _ELLIPSIS + line[-_TAIL_CHARS:]


def matching_lines(ps_output: str) -> list[str]:
    """Return the ``ps`` lines worth reporting, self-references excluded.

    ``ps_output`` is the raw output of ``ps -eo pid,etime,command``, header row
    included; the header is dropped here.
    """
    hits: list[str] = []
    for line in ps_output.splitlines()[1:]:
        if any(marker in line for marker in SELF_MARKERS):
            continue
        if any(pattern in line for pattern in PATTERNS):
            hits.append(condense(line.strip()))
    return hits


def _report(hits: Iterable[str]) -> None:
    """Write the notice for ``hits`` to stderr."""
    hits = list(hits)
    print(
        f"Live background processes owned by this repo are still running "
        f"({len(hits)}). Each one keeps spending whatever it costs, and a "
        f"forgotten harness has already caused one wrong measurement:",
        file=sys.stderr,
    )
    for line in hits[:_MAX_REPORTED]:
        print(f"  {line}", file=sys.stderr)
    if len(hits) > _MAX_REPORTED:
        print(f"  ... and {len(hits) - _MAX_REPORTED} more", file=sys.stderr)
    print(
        "Confirm each is intended; kill anything that is not. Note that "
        "killing a shell does not always kill its Python or Node child.",
        file=sys.stderr,
    )


def main() -> None:
    """Report live repo-owned background processes. Always exits 0."""
    try:
        result = subprocess.run(
            ["ps", "-eo", "pid,etime,command"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        sys.exit(0)

    hits = matching_lines(result.stdout)
    if hits:
        _report(hits)

    sys.exit(0)


if __name__ == "__main__":
    main()
