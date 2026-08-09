#!/usr/bin/env python3
"""Stop hook: surface live background processes owned by this repo.

Rule A4. On the project this framework came from, a background harness that was
believed dead kept running, and the load from its eight concurrent workers was
misread as the cloud provider failing intermittently — a wrong cause, reported to
the human before the real one was found. A process nobody knows is running is also
a live cost, because these harnesses call paid APIs.

Prints a notice on stop when anything matching this repo's harness/server
shapes is still alive. Always exits 0 — this reports, it never blocks.
"""

from __future__ import annotations

import subprocess
import sys

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
_PATTERNS = (
    "pytest",
    "npm run",
    "node ",
    # "uvicorn",              # your dev server
    # "alembic",              # your migration tool
    # "scratch",              # where measurement harnesses run
)

_SELF_MARKERS = ("stop_report_background", "grep ")


def main() -> None:
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid,etime,command"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        sys.exit(0)

    hits: list[str] = []
    for line in out.stdout.splitlines()[1:]:
        if any(marker in line for marker in _SELF_MARKERS):
            continue
        if any(pattern in line for pattern in _PATTERNS):
            hits.append(line.strip()[:200])

    if hits:
        print(
            "Live background processes owned by this repo are still running "
            f"({len(hits)}). Each one keeps spending whatever it costs, and a "
            "forgotten harness has already caused one wrong measurement:",
            file=sys.stderr,
        )
        for line in hits[:12]:
            print(f"  {line}", file=sys.stderr)
        if len(hits) > 12:
            print(f"  ... and {len(hits) - 12} more", file=sys.stderr)
        print(
            "Confirm each is intended; kill anything that is not. Note that "
            "killing a shell does not always kill its Python child.",
            file=sys.stderr,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
