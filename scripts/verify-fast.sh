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

# A placeholder step runs `echo`, which exits 0. Counting it as a pass and then
# printing OK is the same false assurance verify-full.sh used to commit, one
# tier down — and this is the tier that runs dozens of times a day.
todo=0
echo "== lint";  "${LINT[@]}" "$@"
case "${LINT[0]}${LINT[1]-}" in *"TODO: set"*) todo=$((todo + 1));; esac
echo "== tests"; "${TEST[@]}" "$@"
case "${TEST[0]}${TEST[1]-}" in *"TODO: set"*) todo=$((todo + 1));; esac

# The framework's own teeth travel with every stack. Touching a hook, an
# approval script, the file that REGISTERS the hooks, or any of their tests
# runs the hook suite too — the fill-in commands above know nothing about it,
# and a TODO stub passing is not evidence about a guard.
#
# `.claude/settings.json` is in this list for the quietest failure of the set:
# an unregistered hook never runs, and the tests that catch exactly that
# (`test_the_guard_is_registered_in_settings_json` and its siblings) would
# otherwise be skipped by the very edit that breaks them.
case " $* " in
  *".claude/hooks"* | *"tests/hooks"* | *"scripts/approve"* \
  | *"scripts/verify_approvals"* | *".claude/settings.json"*)
    echo "== framework hook tests"
    python3 -m pytest tests/hooks/ -q
    ;;
esac

# Touching a CI example, the exit gate itself, or bootstrap's placeholder list
# can silently desync ci-examples/ from what it claims to run — that is the
# exact failure tests/ci/ exists to catch, so a touch to any of these paths
# has to pay for it here too, not just at the exit gate.
case " $* " in
  *"ci-examples"* | *"tests/ci"* | *"scripts/verify-full.sh"* | *"scripts/bootstrap.sh"*)
    echo "== ci-examples drift tests"
    python3 -m pytest tests/ci/ -q
    ;;
esac

# The Scar Forge's station tracker (scripts/scar_status.py) has its own
# mechanically-checked claims (a closed scar must carry a Station 6 date, a
# scar's Status must not collide with the approval-registry vocabulary) — a
# touch to the tracker, its template, or a scar record itself has to pay for
# re-checking those, same as any other guard in this repo.
case " $* " in
  *"scripts/scar_status.py"* | *"tests/scars"* | *"doc/scars"* | *"doc/templates/SCAR.md"*)
    echo "== scar-forge tests"
    python3 -m pytest tests/scars/ -q
    ;;
esac

if [ "$todo" -ne 0 ]; then
  echo "FAST VERIFY INCOMPLETE — ${todo} of 2 step(s) not configured; they verified NOTHING."
  echo "Fill LINT and TEST in scripts/verify-fast.sh."
  exit 0
fi
echo "FAST VERIFY OK"
