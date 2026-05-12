---
name: refactor-code
version: 1
status: active
purpose: Guide an agent through a behavior-preserving refactor.
applies_to: [codex, claude]
last_updated: 2026-05-11
---

# Refactor Code

## When to Use

Use this when asking an agent to improve structure while preserving behavior.

## Prompt

```text
Refactor the requested code while preserving behavior.

Before editing:
1. Read `AGENTS.md`.
2. Read `mementum/state.md`.
3. Search `mementum/knowledge/` for architecture boundaries, invariants, and workflows.
4. Search `mementum/memories/` for known refactoring pitfalls.
5. Inspect existing tests and identify the smallest validation set.

Refactor rules:
1. Preserve public behavior unless explicitly asked to change it.
2. Keep changes scoped to the stated refactor.
3. Prefer existing local patterns over new abstractions.
4. Add tests only when the refactor exposes missing coverage for risky behavior.
5. Do not mix unrelated cleanup into the refactor.

Before finishing:
1. Run relevant tests when feasible.
2. Summarize the behavioral surface that should be unchanged.
3. Note any validation gaps.
4. Update or propose project memory only if the refactor establishes or changes a durable convention.
```

## Expected Output

- Behavior-preserving refactor.
- Validation summary.
- Explicit note of unchanged behavior assumptions.
- Memory update only for durable conventions or decisions.
