#!/usr/bin/env bash
# Inner loop while iterating. ALWAYS pass the paths you touched — scoping is the whole point
# (on one real project this was 0.49s scoped vs 47.6s unscoped, which is the difference
# between running it every time and quietly skipping it).
#
# Forbidden here and in verify-full.sh: --lf, -x, and -k/-m filtering used to reach green.
# Each can report success while executing nothing.
set -euo pipefail
cd "$(dirname "$0")/.."

# ---- fill these in for your stack -------------------------------------------
LINT=(echo "TODO: set LINT in scripts/verify-fast.sh — e.g. ruff check")
TEST=(echo "TODO: set TEST in scripts/verify-fast.sh — e.g. pytest -q")
# -----------------------------------------------------------------------------

[ $# -eq 0 ] && { echo "usage: $0 <paths…>   (ส่ง path ที่แตะเสมอ)" >&2; exit 2; }
echo "== lint";  "${LINT[@]}" "$@"
echo "== tests"; "${TEST[@]}" "$@"
echo "FAST VERIFY OK"
