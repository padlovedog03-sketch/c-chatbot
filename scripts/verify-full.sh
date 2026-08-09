#!/usr/bin/env bash
# THE EXIT GATE. Run before every handoff.
# A claim without this output does not count — that rule exists because "it works now"
# was said, and believed, about code that had never been run.
set -uo pipefail
cd "$(dirname "$0")/.."

# ---- fill these in for your stack -------------------------------------------
# Each entry: "label|command…"  — add project gates (migrations, contract freshness,
# registry counts) as extra lines rather than folding them into the test command.
STEPS=(
  "lint|echo TODO: set the lint command in scripts/verify-full.sh"
  "format|echo TODO: set the format --check command"
  "tests|echo TODO: set the full test command"
)
# -----------------------------------------------------------------------------

fail=0
echo "EXIT GATE — full verify"
for entry in "${STEPS[@]}"; do
  label="${entry%%|*}"; cmd="${entry#*|}"
  if out=$(eval "$cmd" 2>&1); then
    printf '  %-5s%-18s%s\n' "OK" "$label" "$(printf '%s' "$out" | tail -1)"
  else
    printf '  %-5s%-18s(exit %s)\n' "FAIL" "$label" "$?"
    printf '%s\n' "$out" | tail -30
    fail=1
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "EXIT GATE RED (exit 1)."
  echo "Do not hand off. Diagnose the real cause; do not skip a test, loosen an assertion,"
  echo "or hardcode an expected value to make it pass."
  exit 1
fi
echo "EXIT GATE GREEN. Paste this output in the handoff — a claim without it does not count."
