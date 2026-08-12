#!/usr/bin/env bash
# Register the human's approval of documents, by slug. See scripts/approve.py.
#
#   scripts/approve.sh --list                    # what awaits approval
#   scripts/approve.sh <slug> --by <your-name>   # approve every In Review doc for that slug
#
# Thin wrapper so the typed command stays short; every rule lives in the Python.
# The interpreter is auto-detected: the project's own venv when one exists,
# otherwise whatever python3 is on PATH — a hardcoded `.venv` path made the
# original unusable on any project that manages its environment differently.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -x "${here}/../.venv/bin/python" ]; then
  PY="${here}/../.venv/bin/python"
else
  PY="$(command -v python3)"
fi
exec "$PY" "${here}/approve.py" "$@"
