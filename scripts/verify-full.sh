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
  # The next two are NOT placeholders — do not replace them. The framework's own
  # guards ship with tests whatever your stack is, and if they go red a gate
  # you rely on may be open again.
  "hooks|python3 -m pytest tests/hooks/ -q"
  # Proves the CI examples in ci-examples/ still do what they claim: every
  # command they run for real matches this repo's actual scripts, and the
  # registry/placeholder checks they inline still bite. Before this step
  # existed, ci-examples/ had never been run or tested at all — the layer the
  # whole framework calls "the real enforcement" had never made a sound.
  "ci-examples|python3 -m pytest tests/ci/ -q"
  # Proves scripts/scar_status.py (the Scar Forge's station tracker, NORTH-STAR
  # mechanism ๑) parses this repo's own real scar records correctly and still
  # catches a closed-with-no-trace or out-of-order scar. Also runs the tracker
  # itself: a Closed scar with no Station 6 date, or stations entered out of
  # order, fails this step for real, not just in the test suite.
  "scar-forge|python3 -m pytest tests/scars/ -q && python3 scripts/scar_status.py"
  # Proves scripts/coordinator_lint.py (the mechanically-checked half of the
  # Coordinator Constitution, NORTH-STAR mechanism ๓) still catches an
  # untagged count claim, a truncating MEASURED: command, an untagged
  # instruction, and a missing SELF-REPORT: block.
  "coordinator|python3 -m pytest tests/coordinator/ -q"
)
# -----------------------------------------------------------------------------

fail=0
todo=0
todo_labels=""
echo "EXIT GATE — full verify"
for entry in "${STEPS[@]}"; do
  label="${entry%%|*}"; cmd="${entry#*|}"
  # An unfilled placeholder is neither a pass nor a failure, and must never be
  # printed as "OK". A step whose command is still `echo TODO:` runs nothing,
  # yet an `echo` exits 0 — so the honest-looking version of this loop reported
  # OK three times and then declared the gate GREEN over a build that had not
  # been linted, formatted or tested. That is this framework's first truth
  # (a system reporting success while the truth is elsewhere) committed by the
  # very script whose job is to prevent it.
  if [[ "$cmd" == echo\ TODO:* ]]; then
    printf '  %-5s%-18s%s\n' "TODO" "$label" "not configured — this step verified NOTHING"
    todo=$((todo + 1))
    todo_labels="${todo_labels} ${label}"
    continue
  fi
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

if [ "$todo" -ne 0 ]; then
  # Deliberately exit 0: a fresh clone must not be wedged before bootstrap. But
  # the word GREEN is withheld, because that word is what gets pasted into a
  # handoff as evidence, and it would be evidence of nothing.
  echo "EXIT GATE INCOMPLETE — ${todo} step(s) not configured:${todo_labels}"
  echo "Everything configured passed, and that is ALL this run proves."
  echo "Fill those steps in scripts/verify-full.sh before treating this output as a gate."
  exit 0
fi
echo "EXIT GATE GREEN. Paste this output in the handoff — a claim without it does not count."
