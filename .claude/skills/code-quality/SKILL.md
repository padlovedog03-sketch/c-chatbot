---
name: code-quality
description: Coding and testing standards every implementer and QA agent must follow. Language-agnostic by design — the team fills in the stack-specific half. Use when writing or reviewing any code in this project.
---

# Code quality

Two halves. **The first is fixed** — it does not change with the language and is what the rest of
this framework relies on. **The second is yours to fill in** before the first implementer agent runs.

---

## Part 1 — fixed, regardless of stack

### Tests

- Every new module ships **positive, negative and edge** cases. Edge means whitespace, empty, null,
  zero-versus-absent, and the units or formats your domain confuses (e.g. two spellings of the same
  currency).
- **A new test must be proven to fail.** Break the thing it guards, watch it go red *naming the
  thing*, restore, confirm no residue. A test that was green before the fix is worse than no test:
  it is confidence with nothing behind it.
- **Assert the reason, not only the outcome.** `assert status != "PASS"` also passes when the code
  crashed. Assert the message or the reason code the caller will actually act on.
- **Beware proving the wrong thing red.** When reverting a fix to prove a test bites, check that the
  revert restores the *original* condition rather than making some other branch unreachable — a
  malformed revert makes a different test fail, which looks exactly like success. Count occurrences
  before and after if the revert is not a single-line swap.
- Tests must pass **alone and in any order**. A test that only passes after its neighbours is a
  dependency you have not noticed yet.

### Failure behaviour

- **Empty, unknown and zero are three different answers.** An empty list is `[]`, never `null` and
  never a missing key. A value nobody supplied must never silently become `0`, `""` or "passed".
- **Never report success for work not done.** If a check could not run, say it could not run and
  why. The reason is what the reader acts on — a wrong reason sends them chasing the wrong thing.
- **Specific exceptions only.** No bare catch-alls. External calls get a timeout and a bounded
  retry. Validation errors name the field.
- **Fail loudly at the boundary.** Reject an unknown key rather than ignoring it; a request that
  silently drops half its payload and returns success is the most expensive bug shape there is.

### Structure

- No magic numbers or strings. Thresholds, tolerances and keyword lists live in configuration, with
  a comment citing the rule they implement.
- Nothing environment-specific in code: no endpoints, resource names, connection strings, region
  codes, tenant or subscription identifiers. Read them from configuration or environment variables.
- **No secrets anywhere** — not in source, tests, fixtures, documentation or commit messages.
  Document the variable name instead.
- Types on public signatures; a docstring on every public module, class and function saying what it
  does and, where it is not obvious, *why*.
- Structured logging through the shared logger, never bare prints. Include a request identifier.
  **Log field names and counts, never values** — a value may be personal data.

### Changes

- Touch only what the task requires. Every changed line should trace to the request.
- Remove imports and helpers **your** change orphaned. Leave pre-existing dead code alone and
  mention it instead.
- Match the surrounding style even where you would write it differently.

---

## Part 2 — fill this in for your stack

Replace the placeholders. Keep it short; this is a checklist, not a style guide.

**Language and version:** `<e.g. Python 3.12 / Node 20 + TypeScript 5>`

**Commands** (these must match `scripts/verify-fast.sh` and `verify-full.sh` exactly — if they drift,
the gate stops meaning anything):

| purpose | command |
|---|---|
| lint | `<...>` |
| format check | `<...>` |
| test (scoped) | `<...>` |
| test (full) | `<...>` |
| type check | `<...>` |

**Layout:** `<where source lives, where tests live, how they mirror each other>`

**Framework-specific rules:** `<e.g. async handlers must not block the event loop; database access
only through the ORM's parameterised queries; no eval; dependencies pinned>`

**Forbidden in this codebase:** `<e.g. a banned library, a deprecated API with its removal date, a
pattern the team has decided against — and the reason, so nobody reintroduces it>`
