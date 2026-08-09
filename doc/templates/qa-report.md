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
