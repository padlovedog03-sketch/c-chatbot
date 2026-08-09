#!/usr/bin/env python3
"""Stop hook: surface live background processes owned by this repo.

Rule A4. A background harness that was believed dead kept running and its
eight concurrent judges were misread as an Azure transient-failure rate — a
wrong conclusion reported to the user before the real cause was found. A
process nobody knows is running is also a live cost: these harnesses call
Azure OpenAI.

Prints a notice on stop when anything matching this repo's harness/server
shapes is still alive. Always exits 0 — this reports, it never blocks.
"""

from __future__ import annotations

import subprocess
import sys

# Shapes worth reporting: our dev server, alembic, pytest, and any Python
# running out of the scratchpad (where the measurement harnesses live).
_PATTERNS = (
    "run-backend-dev.sh",
    "uvicorn",
    "alembic",
    "pytest",
    "scratchpad",
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
            f"({len(hits)}). Each one may be spending Azure quota, and a "
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
