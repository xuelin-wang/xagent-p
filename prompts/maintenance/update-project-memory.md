---
name: update-project-memory
version: 1
status: active
purpose: End-of-task prompt for deciding whether to update project memory.
applies_to: [codex, claude]
last_updated: 2026-05-11
---

# Update Project Memory

## When to Use

Use this at the end of a task to decide whether durable project memory should change.

## Prompt

```text
Decide whether this task produced a durable project-memory update.

Review:
1. The user's request.
2. Files changed during the task.
3. Tests or validation performed.
4. Existing `mementum/state.md`.
5. Relevant knowledge and memory files under `mementum/`.

Update memory only if one of these is true:
- a design decision was made
- a previous assumption was corrected
- a bug revealed a reusable lesson
- a convention became important
- a workflow should be repeated
- an implementation pitfall should be avoided
- an open question was resolved or newly discovered

Choose the right destination:
- `mementum/state.md` for current direction, blockers, next steps, recent decisions
- `mementum/memories/` for one short durable lesson
- `mementum/knowledge/` for synthesized design, workflow, testing, security, or architecture context

Do not add routine summaries, temporary notes, obvious facts, speculation, secrets, runtime data, raw logs, private data, or large generated artifacts.

After editing, report:
1. Memory files updated.
2. Why each update was durable.
3. Source pointers used.
4. Confirmation that no sensitive/runtime data was added.
```

## Expected Output

- Memory update or explicit no-update decision.
- Rationale for the decision.
- Source pointers.
