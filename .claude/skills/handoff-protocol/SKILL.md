---
name: handoff-protocol
description: File-based handoff conventions between the PM, BA/SA, AI Engineer, and QA agents. Use when producing or consuming any document in doc/ so the next agent in the pipeline can pick up work without extra context.
---

# Handoff Protocol

Agents share no memory — all context passes through files in `doc/`. A handoff is complete only when the next agent could start from the files alone.

## Pipeline and Ownership

```
PM ──PRD──▶ 👤 ──▶ BA/SA ──spec+design──▶ 👤 ──▶ AI Engineer ──code+tests──▶ 👤 ──▶ QA ──report──▶ 👤 ──▶ Done
                                                        ▲                                │
                                                        └──────── fail: defects ─────────┘
```

Every `👤` is a **human approval gate** — no stage starts until the human has approved the previous stage's artifact.

| Directory | Owner | Artifact | Naming |
|---|---|---|---|
| `doc/requirements/` | pm | PRD | `PRD-<feature-slug>.md` |
| `doc/tasks/` | pm | Backlog | `backlog.md` |
| `doc/specs/` | ba-sa | Functional spec | `SPEC-<feature-slug>.md` |
| `doc/architecture/` | ba-sa | Technical design / ADR | `DESIGN-<feature-slug>.md` |
| `doc/qa/` | qa | QA report | `QA-<feature-slug>.md` |

Use the same `<feature-slug>` (lowercase, hyphenated) across the whole chain so artifacts link up.

## Document Rules

1. **Always start from the template** in `doc/templates/`. Don't invent your own structure.
2. **Status header** at the top of every document:
   `Status: Draft | In Review | Approved | Done`
3. **Upstream link**: every document names the file it derives from (spec → PRD, design → spec, QA report → spec). A document with no upstream link is an orphan — fix it.
4. **Only the owner edits.** Found a problem in another role's document? Report it in your handoff message; don't edit it yourself.

## Human Approval Gate

Status lifecycle: `Draft` → `In Review` → `Approved` → `Done`. Only the **human** (via the orchestrator) moves a document past `In Review`.

Rules for every agent:

1. **Before starting**: read your upstream document's status header. If it is not `Status: Approved`, STOP immediately and report: "Upstream <file> is at <status> — needs human approval before I can start." Do not work from unapproved input.
2. **When finishing**: set your own artifact to `Status: In Review` — never `Approved`, even if you're confident. Approving your own work defeats the gate.
3. **Revisions**: if the human requests changes, revise the same document (keep `Status: Draft` while working, back to `In Review` when done).
4. **AI Engineer stage** (no document artifact): the code diff + handoff message is the review artifact; the orchestrator must get human approval before invoking `qa`.

## Handoff Message

Your final message when finishing a task must contain:

1. **Artifacts**: exact paths of files created/modified.
2. **Evidence**: verification results (from the engineering loop).
3. **Assumptions**: anything you decided that the human or next agent should know.
4. **Next step**: which agent should act next and on what input.
