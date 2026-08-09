---
name: engineering-loop
description: Verify-driven work loop mandatory for every agent (PM, BA/SA, AI Engineer, QA) on any non-trivial task. Use when starting a task to define verifiable success criteria, then iterate execute→verify→fix until all criteria pass or the iteration cap is hit.
---

# Engineering Loop

Every task runs as a loop against verifiable success criteria. Claims without evidence are worthless — only executed checks count.

## The Loop

```
DEFINE DONE → PLAN → EXECUTE → VERIFY (fast tier) → pass? → EXIT GATE (full tier) → REPORT with evidence
                        ▲          │
                        └─DIAGNOSE─┘ (max 5 iterations)
```

### 1. Define Done (before any work)

Write down success criteria that a machine or checklist can verify:

- **Code**: the two verify tiers below, plus any task-specific command.
- **Documents**: the role-specific checklist from your agent definition (PRD checklist, spec traceability, QA verdicts).

Weak criteria ("make it work", "improve the doc") are not allowed — rewrite them until they're binary pass/fail.

### 2. Plan

Smallest sequence of steps that reaches the criteria. For multi-step work:

```
1. [step] → verify: [command/check]
2. [step] → verify: [command/check]
```

### 3. Execute

One step at a time. Small steps make failures easy to localize.

### 4. Verify — two tiers, and they are not interchangeable

| | command | when | what it costs |
|---|---|---|---|
| **fast tier** (inner loop) | `scripts/verify-fast.sh <paths>` — **always pass the paths you touched** | after every change while iterating | measured: `tests/infra/` 0.49s · one test file 0.45s · whole suite with no path 47.6s |
| **exit gate** | `scripts/verify-full.sh` | before **every** handoff, no exceptions | ~65s; adds `real_sleep` tests, `ruff format --check`, registry counts, alembic up/down/up |

**Actually run the check.** Never mark a criterion passed from reasoning alone. Read the real output.

**Pass the paths.** `scripts/verify-fast.sh` with no argument runs the whole suite — 47.6s measured — while `scripts/verify-fast.sh tests/infra/` runs the two files that cover Bicep and env mapping in **0.49s**. Same script, ~70x. The speed already exists; forgetting the argument is what costs the time, and over a day of iterating that is the single largest avoidable delay in the loop. Scoping the *inner* loop is not narrowing the gate: the exit gate below always runs everything.

The fast tier is a convenience, never a claim. A handoff that pastes fast-tier output is not verified. Things that are **forbidden** in either tier, because each one can report success while executing nothing:

- never `--lf` / `--last-failed` — after a green run these select zero tests and exit 0.
- `-x` — hides the other failures and turns one iteration into ten.
- `-k` filtering or extra `-m` deselection as a way to "get green".

### 5. Iterate on Failure

- Read the actual error — don't guess.
- Diagnose the root cause before changing anything.
- Fix the cause, not the symptom. Forbidden: skipping tests, loosening assertions, deleting checks, hardcoding expected outputs.
- Re-run the same verification.
- **Cap: 5 iterations on the same failing criterion.** If still failing, stop. A truthful blocker report is a successful outcome; a fake pass is a failure.

### 6. Report

End with evidence:

- Which criteria passed — with the `scripts/verify-full.sh` output that proves it.
- Which failed or were blocked — with the actual error and your diagnosis.
- Never say "should work", "probably passes", or "done" without a run.

---

## Failure modes this project has already hit

Each of these cost real time on this codebase. They are written as checkable conditions, not advice — answer each one before reporting.

**1. Silent failure is the dominant defect class here.**
For every new code path, ask: *what does this emit when it goes wrong, and is that distinguishable from success?* An empty list, a `0`, a default value and a `None` must never be able to mean "it broke". Real instances: Azure F0 truncated an 18-page document to 2 pages with no error; `FieldExtractionService.extract()` swallowed LLM failures into `[]`, so a timeout was recorded as recall 0.000 — a *measurement*, not an error; money coercion failed on the English word "Baht" and set confidence to 0.0, dropping correct values below the autofill floor.
→ Check: name the failure signal for each new path. If the answer is "it returns empty", that is a defect, not a design.

**2. A guard you have not broken on purpose is not a guard.**
Green tests prove nothing about whether an assertion has teeth. Real instance: a frontend field-contract assertion had been removed, so the contract sat stale for 18 days with a green suite.
→ Check: inject the violation the guard exists to catch (a phantom field, a truncated file, a fake manifest entry), show it goes **red naming the violation**, revert, show green, and confirm zero residue with `grep -c`.

**3. Never discard uncommitted work.**
One `git checkout <path>` on a dirty tree destroyed a wave of config edits and took the suite from 1297 passed to 164 failed. This is now blocked by `.claude/hooks/guard_bash.py`.
→ Check: `git stash` or commit before any discard. If the discard is genuinely intended, use the `ALLOW_DESTRUCTIVE=1` prefix so the choice is on the record.

**4. Do not relay a number you did not verify.**
Numbers from a subagent, a heuristic script, or an earlier message get quoted as fact and reach the human wrong. Real instances: "~19 fields" and "159/7 <PROJECT>-confirmed" were relayed; the real values were 22 and 82/5/125.
→ Check: before any count reaches a report, re-derive it with your own command, and sanity-check it against two or three facts you already know.

**5. Never fuzzy-match an authoritative mapping.**
A `difflib` matcher over Thai field labels reported "77 fields the Excel has that we don't", including fields that demonstrably existed. Thai catalogs phrase the same field differently, so surface similarity is uninformative.
→ Check: fuzzy matching may rank candidates for a human or an LLM to judge. It may never decide an add/remove. That work is `ba-sa` reading rows.

**6. PDPA: describe shapes, never quote real identifiers.**
Two separate waves leaked real data into *docstrings documenting a finding* — real 13-digit juristic registration numbers, a real company name, real country tokens as OCR-corruption examples. The intent was legitimate every time, which is exactly why prose guidance fails.
→ Check: reproduce the example with a synthetic string of the same shape/length. Then scan tracked files only: `git ls-files | xargs grep -ilE "<pattern>"` — scanning the working tree includes the git-ignored source documents and buries the signal. Publicly-registered identifiers count too.

**7. Do not measure a tree another agent is editing.**
A premise was reported wrong twice because the measurement was taken while a subagent was mid-edit.
→ Check: before measuring, confirm no agent owns the files. If one does, wait for its report.

**8. A background process you believe is dead may not be.**
Killing a shell does not always kill its Python child. Eight concurrent judges from a duplicated harness were misread as an Azure transient-failure rate, and a wrong conclusion reached the human. The Stop hook now reports live processes.
→ Check: after killing anything, verify with `ps`, not with the kill command's exit code.
