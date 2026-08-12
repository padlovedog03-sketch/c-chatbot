# SCAR: <short title — the mistake, not the fix>

Status: Open | In Forge | Closed
Upstream: <the commit / incident / report this scar comes from, or "original incident — no prior document">
Opened: YYYY-MM-DD

<!--
This is a เกล็ดแผล (scar) record — the unit the Scar Forge (NORTH-STAR mechanism
๑) moves through six fixed stations, each with an owner and a checkable
result:

    เหตุการณ์ที่พลาด → บทเรียน → กฎ → กลไก → พิสูจน์ว่ากลไกร้องได้จริง → ด่านที่ปิดแล้วทิ้งรอย

`scripts/scar_status.py` reads every file in `doc/scars/` and computes, per
scar, which station it is CURRENTLY at (the highest-numbered station whose
`Entered:` line is a real date) and how long it has sat there — and, across
all scars, the average time from Station 1 to Station 4. That is the one
number NORTH-STAR names as the actual measure of success, so the dates below
are not decoration:

  - Fill `Entered:` with a real `YYYY-MM-DD` only when a station is ACTUALLY
    reached — a filled-in station with an unfilled date undercounts how long
    it sat there; an unfilled station with a filled-in date invents progress
    that did not happen.
  - Leave later stations' `Entered:` lines as the literal `YYYY-MM-DD` until
    they are genuinely reached. The tracker treats that literal string as
    "not yet entered" — it does not parse as a date, on purpose.
  - `Status: Closed` belongs on this document only once Station 6 has a real
    date. A scar closed at any earlier station is a rule with no mechanism,
    or a mechanism with no proof it bites — exactly the shape NORTH-STAR
    calls "โฆษณาเกินความสามารถ" (worse than not having it).

Deliberately NOT `Status: Draft | In Review | Approved | Done | Living` (the
vocabulary `.claude/skills/handoff-protocol/SKILL.md` and the approval
registry use): a scar is not a PM/BA-SA/Engineer/QA artifact and does not go
through human approval to progress — it closes on EVIDENCE (a mechanism that
demonstrably exists and a test that demonstrably bites), which is
mechanically checkable, not a judgement call. Using a different vocabulary is
what keeps `scripts/verify_approvals.py` and the CI registry gate from ever
mistaking a closed scar for an unapproved spec — they scan for the literal
words `Approved`/`Done`, which a scar's `Status:` line will never contain.
-->

## Station 1 — เหตุการณ์ที่พลาด (Incident)

Entered: YYYY-MM-DD
Owner: <who found it>

<What happened, concretely. A command, a commit, a screenshot, an exact
output — not a paraphrase. If this scar was cut from an existing commit or
report, link it here instead of re-describing it from memory.>

## Station 2 — บทเรียน (Lesson)

Entered: YYYY-MM-DD
Owner: <who wrote the lesson>

Cost (measured, not estimated — the command or record that produced the number):

<What it actually cost. "It could have been bad" is not a lesson. A number
with the command that produced it is.>

## Station 3 — กฎ (Rule)

Entered: YYYY-MM-DD
Owner: <who wrote the rule>

<One sentence. Actionable — something a person or a mechanism can check
against a concrete case — not a sermon.>

## Station 4 — กลไก (Mechanism)

Entered: YYYY-MM-DD
Owner: <who built it>

<Exact path to the file/hook/script/test that enforces the rule. "We'll
remember" is not a mechanism.>

## Station 5 — พิสูจน์ว่ากลไกร้องได้จริง (Proof it bites)

Entered: YYYY-MM-DD
Owner: <who ran the injection>

<The injection: what was broken on purpose, the exact red output naming the
violation, the revert, and the green run after. A mechanism with no injection
record on file counts as unproven, per NORTH-STAR สัจธรรม ๒.>

## Station 6 — ด่านที่ปิดแล้วทิ้งรอย (Closed gate, trace left)

Entered: YYYY-MM-DD
Owner: <who closed it>

<The permanent trace that keeps this from regressing silently: the test
file + function name, and the commit that shipped it. Once this station has
a real date, set `Status: Closed` above.>
