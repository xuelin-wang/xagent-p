---
name: implement-feature
version: 1
status: active
purpose: Guide an agent through a feature implementation with tests and memory hygiene.
applies_to: [codex, claude]
last_updated: 2026-05-11
---

# Implement Feature

## When to Use

Use this when asking an agent to implement a new feature or meaningful behavior change.

## Prompt

```text
Implement the requested feature in this repository.

Before editing:
1. Read `AGENTS.md`.
2. Read `mementum/state.md`.
3. Search `mementum/knowledge/` and `mementum/memories/` for relevant context.
4. Inspect existing code and tests for established patterns.
5. Identify the smallest safe implementation path and relevant validation commands.

During implementation:
1. Preserve existing behavior unless explicitly asked to change it.
2. Keep changes scoped and consistent with existing architecture.
3. Add or update focused tests when behavior changes.
4. Do not commit secrets, runtime data, logs, private data, or large generated artifacts.

Before finishing:
1. Run relevant validation when feasible.
2. Summarize changed files and validation results.
3. Note any tests that could not be run.
4. Decide whether a durable project lesson was learned.
5. If yes, propose or make a concise `mementum/` update.

Do not update project memory for routine edits, temporary facts, or obvious details.
```

## Expected Output

- Implemented feature.
- Focused tests or explanation for missing tests.
- Validation summary.
- Memory update or explicit note that no durable lesson was added.
