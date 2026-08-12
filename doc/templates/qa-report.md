# QA Report: <Feature Name>

Status: Draft
Owner: qa
Upstream: doc/specs/SPEC-<feature-slug>.md
Date: YYYY-MM-DD

## Verdict: PASS | FAIL

<One sentence summary. FAIL if any criterion fails.>

## Criteria Results

| # | Criterion | Verdict | Evidence (test / command) |
|---|---|---|---|
| AC1 | <short name> | PASS/FAIL | tests/test_x.py::test_y — output summary |

## Test Run

```
<final pytest command + summary line, e.g. "12 passed in 0.34s">
```

## Defects (if FAIL)

| Severity | Description | Where | Suggested owner |
|---|---|---|---|
| High/Med/Low | <what breaks, how to reproduce> | src/<PACKAGE>/x.py:42 | ai-engineer |

## Edge Cases Probed

- <case> → <result>

## Approval history

<!-- scripts/approve.sh writes the approval entry here. Leave this heading in
     place: approve.py REFUSES any document that lacks it, because an approval
     with no record of what wording it replaced is an approval nobody can audit
     later. Dates and amendment history belong here — never decorated onto the
     canonical `Status:` line, whose grammar is machine-checked. -->

- **YYYY-MM-DD — drafted.** <who, and what this first version was based on.>
