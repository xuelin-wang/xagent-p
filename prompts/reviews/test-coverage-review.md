---
name: test-coverage-review
version: 1
status: active
purpose: Review whether changed behavior has adequate validation.
applies_to: [codex, claude]
last_updated: 2026-05-11
---

# Test Coverage Review

## When to Use

Use this when a branch changes behavior and you want to know whether tests and validation are sufficient.

## Prompt

```text
Review test coverage and validation for the current branch.

Inspect:
1. Branch diff against `main`.
2. Relevant tests and fixtures.
3. `mementum/knowledge/testing-and-evaluation.md` if present.
4. Related source files that define behavior.

Assess:
- changed behavior with no focused tests
- tests that assert implementation details instead of behavior
- missing regression tests for bug fixes
- missing provider/config/deployment validation where relevant
- live tests that should stay opt-in
- generated artifacts or snapshots that may be stale
- validation commands that should be run before merge

Output:
1. Coverage gaps first, ordered by risk.
2. File and line references where possible.
3. Suggested tests or validation commands.
4. Any validation that cannot be automated.

Do not modify files unless explicitly asked.
```

## Expected Output

- Coverage findings.
- Suggested tests or validation commands.
- Residual manual-validation notes.
