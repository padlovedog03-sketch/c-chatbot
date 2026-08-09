---
name: coordinator-discipline
description: Mechanical pre-flight checks for the coordinating assistant (the main thread) before asserting a fact, briefing an agent, approving work, or reporting to the human. Use on every turn that makes a factual claim, dispatches an agent, or relays an agent's findings — the coordinator is the only actor in this pipeline with no guard, and is measurably the one most often wrong.
---

# Coordinator discipline

Every other artefact in `.claude/` governs an agent. Nothing governed the coordinator, and over two
days of autonomous work the coordinator made **14 wrong assertions — every one caught by someone
else, none self-caught.** This file is the missing guard. It is not advice; each rule names the
failure that produced it and the command that prevents it.

## 1. Absence and quantity claims

**Rule: never claim "there is no X", "nothing uses X", or "there are N X" from a command that could
not have seen all of X.**

Before such a claim, re-run with: no `limit`, no `head`/`tail`, no `[:n]`, no `-m`/`-k`, no broad
`OR` pattern, no `2>/dev/null`, and paths verified to exist. Then paste the command next to the
number.

Failures this rule exists for:
- Reported a crash occurred **2 times**; a `limit: 10` had truncated it. Real figure: **35**. Two
  means "one-off, note it"; thirty-five means "fires on every keystroke".
- `grep -rn X app/ components/ 2>/dev/null` reported **2 files**. `components/` did not exist; the
  error went to `/dev/null`. Real figure: **4**, including a site nobody had examined.
- A pattern of `Maximum update depth|useEffect|setState|out-of-range|Warning` matched 793 unrelated
  warnings and hid the error being looked for. **A broad OR pattern is a truncating filter in
  disguise.**

**`2>/dev/null` is banned in any command whose output will become a claim.** It converts "the path
is wrong" into "the answer is zero".

## 2. Structural and causal claims

**Rule: a claim about a structure requires reading the structure, not its summary. A claim about a
cause requires the discriminating contrast, not a plausible story.**

- Read the **cells**, not the header row, before describing a table's shape. Reported that a <PROJECT>
  raw-material row carried both sources and 12 figures, and that a committed spec therefore had the
  wrong shape. The two labels were **row-block labels in column 0**; a row is 8 inputs for one
  source. The spec was right.
- A count is not a cause. Reported "exactly 5 rows per source is the fingerprint of a truncated
  transcription". Five is **the form's capacity** — evidence of fidelity, the opposite conclusion.
- Read the field's definition before describing its behaviour. Reported that 8 of 10 fields "have no
  checker" from `impl=None`. `check_method` is the mandatory field; `impl` is an override that is
  `None` on **212 of 221** fields.
- Check whether a value is stored before calling a change risky. Reported that redefining
  `populated` "moves every historical completeness figure". It is computed on read, stored nowhere,
  and gates nothing.

## 3. Bookkeeping under throughput

These drop silently when many agents are in flight. They are the cheapest failures to prevent and
the most expensive to discover.

- **Commit an agent's handback before dispatching anything else into that repo.** 741 finished lines
  sat uncommitted while the next agent was briefed that "the repo has not moved at all". It found
  them and built around the false premise; a less careful agent would have destroyed them.
- **Never describe a repo's state from memory.** Run `git log --oneline -1` and
  `git status --porcelain` and quote them.
- **When a document's status changes, re-read every artefact that asserted something about its old
  status.** Three traceability-allowlist entries said "nothing is built" about specs approved and
  shipped hours later — written, then approved, by the coordinator, and left standing.
- **Approving and shipping on the same day removes the review window the gate exists to create.** The
  gate still passes in form. Nobody independent has read the thing.
- **Check who owns a requirement before assigning it.** Mis-scoped an item to `ba-sa` by carrying a
  requirement number across from a different spec without reading it.

## 4. Applying what is already known

The most expensive failures were not ignorance. The knowledge existed, in memory, written by the
coordinator, and was not applied under load.

- A memory says *test the path the user takes*. The flow walk was then scheduled **last**, behind
  weeks of test-writing — while the three worst defects of the week were all found by a human
  walking the UI, and were missed by 2,855 backend tests and 42 browser specs.
- **Default: probe the real path cheaply first, then build tests around what it finds.** A green
  suite is evidence about the suite.

## 5. Relaying an agent's findings

- **Re-derive any number before repeating it.** Say "unverified, from the agent" when it has not been
  re-derived.
- **State provenance for every constraint given to an agent**: approved spec, owner instruction, or
  the coordinator's own judgement. A coordinator's brief never outranks an approved spec, and saying
  which is which lets the agent push back correctly.
- **An agent that contradicts the coordinator is the most valuable output available.** Over two days,
  every correction from an agent was right and every one prevented shipped harm. Brief agents to
  contradict, and never smooth a correction away when reporting it to the human.

## 6. Reporting to the human

- Failures are reported verbatim, including the coordinator's own.
- A number about the wrong path is worse than no number. State which path was exercised.
- If a measurement is flattering, check the route before reporting it.
- Never report a percentage of completion derived from a path not walked end to end.
