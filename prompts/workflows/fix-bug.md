---
name: fix-bug
version: 1
status: active
purpose: Guide an agent through diagnosing and fixing a bug.
applies_to: [codex, claude]
last_updated: 2026-05-11
---

# Fix Bug

## When to Use

Use this when asking an agent to investigate and fix a defect.

## Prompt

```text
Investigate and fix the reported bug.

Before editing:
1. Read `AGENTS.md`.
2. Read `mementum/state.md`.
3. Search `mementum/knowledge/` and `mementum/memories/` for related pitfalls, invariants, and workflows.
4. Reproduce or localize the bug from tests, logs supplied by the user, or source inspection.
5. Identify the smallest behavior-preserving fix.

Implementation rules:
1. Add a regression test when practical.
2. Keep the fix scoped to the failing behavior.
3. Do not rewrite adjacent code unless required for the fix.
4. Do not add secrets, runtime data, private data, raw logs, or large generated artifacts.

Before finishing:
1. Run the focused regression test and relevant nearby tests when feasible.
2. Summarize root cause, fix, and validation.
3. If the bug revealed a reusable lesson or pitfall, update or propose an update to `mementum/`.
```

## Expected Output

- Root-cause summary.
- Minimal fix.
- Regression test or reason it was not added.
- Validation summary.
- Memory update only when the lesson is durable.
