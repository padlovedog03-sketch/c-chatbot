# SPEC: <Feature Name>

Status: Draft
Owner: ba-sa
Upstream: doc/requirements/PRD-<feature-slug>.md
Date: YYYY-MM-DD

## Overview

<Two or three sentences: what will exist when this is done.>

## Acceptance Criteria

| # | Maps to | Given / When / Then | Test file |
|---|---|---|---|
| AC1 | R1 | Given <state>, When <action>, Then <outcome> | tests/test_<module>.py |

## Functional Behavior

<Detailed behavior: inputs, outputs, validation, error cases.>

## Technical Design

- **Files to create/modify**: <exact paths>
- **Interfaces**: <function/class signatures, 3.12-compatible>
- **Data**: <structures, persistence if any>

## Decisions (ADR-style)

- **<Decision>** — Context: <...> Decision: <...> Consequences: <...>

## Traceability

R1 → AC1; R2 → AC2, AC3 <every PRD requirement must appear>

## Approval history

<!-- scripts/approve.sh writes the approval entry here. Leave this heading in
     place: approve.py REFUSES any document that lacks it, because an approval
     with no record of what wording it replaced is an approval nobody can audit
     later. Dates and amendment history belong here — never decorated onto the
     canonical `Status:` line, whose grammar is machine-checked. -->

- **YYYY-MM-DD — drafted.** <who, and what this first version was based on.>
