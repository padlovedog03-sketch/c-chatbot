# SCAR: the exit gate printed GREEN over three steps that ran nothing

Status: Closed
Upstream: commit 054f94f ("fix: the exit gate stopped saying GREEN over steps that ran nothing"), re-verified during wave 2's audit of the Scar Forge itself
Opened: 2026-08-12

<!--
Worked example for `doc/templates/SCAR.md` / `scripts/scar_status.py`, run
through all six stations against material that already existed in this
repo's own commit history — chosen because it is this framework's clearest
self-inflicted instance of NORTH-STAR สัจธรรม ๑ (a system reporting success
while the truth is elsewhere), committed by the one script whose entire job
is to prevent exactly that.
-->

## Station 1 — เหตุการณ์ที่พลาด (Incident)

Entered: 2026-08-12
Owner: wave 1 build (caught during its own dogfooding, before shipping)

`scripts/verify-full.sh`, before commit `054f94f`, shipped three of its four
steps as `echo TODO: …` placeholders. `echo` exits `0`, so the loop's only
branch (`if out=$(eval "$cmd" 2>&1); then … OK …`) counted each placeholder
as a pass.

Re-measured directly for this record — checked out the exact pre-fix file
(`git show 054f94f^:scripts/verify-full.sh`) and ran it for real against this
repo, rather than trusting the commit message's quoted transcript:

```
$ bash /tmp/old_verify_full.sh
EXIT GATE — full verify
  OK   lint              TODO: set the lint command in scripts/verify-full.sh
  OK   format            TODO: set the format --check command
  OK   tests             TODO: set the full test command
EXIT GATE GREEN. Paste this output in the handoff — a claim without it does not count.
measured exit code: 0
```

## Station 2 — บทเรียน (Lesson)

Entered: 2026-08-12
Owner: wave 1 build

Cost (measured, not estimated — the command that produced the number is in
Station 1 above): of the 3 non-hook steps the gate claims to verify, **0
executed**. 100% of the claimed lint/format/test coverage was manufactured
entirely by `echo`'s exit code, and the final line told the reader to paste
this exact output as evidence a change had been checked.

Stated plainly, per NORTH-STAR's own honesty rule: this was caught during the
same wave's dogfooding, before any real handoff pasted the output — the cost
that WOULD have been paid (a reviewer trusting a GREEN that verified nothing)
is a stated risk, not an incurred one. Recording that distinction here rather
than rounding it up to a bigger story is itself an application of the rule
this scar produces.

## Station 3 — กฎ (Rule)

Entered: 2026-08-12
Owner: wave 1 build

A verification gate must never print its all-clear word over a step whose
command did not actually execute the check it claims to run. An unfilled or
trivially-true step must be labelled as unverified, and the final verdict
must use a visibly different word than the one used for a fully verified run
— never the same word, softened by context.

## Station 4 — กลไก (Mechanism)

Entered: 2026-08-12
Owner: wave 1 build

`scripts/verify-full.sh:41-46` — before evaluating a step's command, checks
whether it is still the literal `echo TODO:` placeholder shape; if so, prints
`TODO … not configured — this step verified NOTHING`, increments a `todo`
counter, and `continue`s past the OK/FAIL branch entirely, so a placeholder
can never reach the code path that would label it `OK`.

`scripts/verify-full.sh:63-70` — the final verdict is now three-way, not
two-way: `fail>0` → `EXIT GATE RED`; else `todo>0` → `EXIT GATE INCOMPLETE`
(exit 0, but the word `GREEN` is withheld — deliberately, because that word
is what gets pasted as evidence); else → `EXIT GATE GREEN`.

`scripts/verify-fast.sh:21-26,44-48` carries the identical fix one tier down,
for the same reason: it runs "dozens of times a day," so a false OK there is
repeated far more often than at the exit gate.

## Station 5 — พิสูจน์ว่ากลไกร้องได้จริง (Proof it bites)

Entered: 2026-08-12
Owner: wave 1 build; re-injected and re-measured during wave 2's audit

Original wave-1 record (`tests/hooks/test_verify_scripts.py`, docstring of
`test_the_gate_never_says_green_while_a_step_is_an_unfilled_placeholder`):
with the `echo TODO:` branch removed — the exact shape the script shipped in
— that test and `test_a_placeholder_step_is_labelled_todo_not_ok` both went
red, because the gate printed `OK` three times and then `EXIT GATE GREEN`.

**Re-verified for this record, not trusted from the docstring alone** (per
wave 2's own standing rule to check inherited claims before repeating them):
removed the identical branch from the CURRENT `scripts/verify-full.sh` and
reran the full suite. Measured result — **3 tests red, not 2**, because a
third test now exists that did not exist when the original record was
written (`tests/ci/test_ci_examples.py::test_gate_2_extracted_command_actually_runs`,
added in wave 2's own CI-examples audit):

```
FAILED tests/hooks/test_verify_scripts.py::test_the_gate_never_says_green_while_a_step_is_an_unfilled_placeholder
FAILED tests/hooks/test_verify_scripts.py::test_a_placeholder_step_is_labelled_todo_not_ok
FAILED tests/ci/test_ci_examples.py::test_gate_2_extracted_command_actually_runs
3 failed, 179 passed
```

Reverted (`git diff --stat scripts/verify-full.sh` showed an empty diff —
byte-for-byte restoration), reran: `183 passed`. The mechanism has grown a
second, independent line of defense since it was first proven — worth
recording as an update rather than silently repeating the older "2 tests"
figure, per the same rule that produced this proof in the first place.

## Station 6 — ด่านที่ปิดแล้วทิ้งรอย (Closed gate, trace left)

Entered: 2026-08-12
Owner: wave 2 (Scar Forge worked example)

Permanent traces, both already on `main`:

- `tests/hooks/test_verify_scripts.py::test_the_gate_never_says_green_while_a_step_is_an_unfilled_placeholder`
  and `::test_a_placeholder_step_is_labelled_todo_not_ok` — shipped in commit
  `054f94f`.
- `tests/ci/test_ci_examples.py::test_gate_2_extracted_command_actually_runs`
  — shipped in commit `94ba28e`, an independent re-derivation of the same
  property from the CI-examples audit, not a copy of the first two.

This record itself is the third trace: the first scar entered into
`doc/scars/` after `scripts/scar_status.py` existed to read it, proving the
forge's six stations run end to end on real material rather than a
hypothetical.
