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
