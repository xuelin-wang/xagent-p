---
name: orient-repo
version: 1
status: active
purpose: Orient an agent before major repository work.
applies_to: [codex, claude]
last_updated: 2026-05-11
---

# Orient Repo

## When to Use

Use this at the start of a substantial or ambiguous task when the agent needs repo context before proposing or editing.

## Prompt

```text
Orient yourself in this repository before making changes.

Please:
1. Read `AGENTS.md` and `CLAUDE.md` if present.
2. Read `mementum/state.md` if present.
3. Search `mementum/knowledge/` for relevant design, workflow, testing, security, and open-question context.
4. Search `mementum/memories/` for known pitfalls or durable lessons.
5. Inspect the relevant source, tests, docs, scripts, and configuration files.
6. Summarize the repository areas relevant to the task.
7. Identify likely validation commands.
8. List assumptions and items to verify.

Do not edit files during orientation unless explicitly asked.
Do not store secrets, runtime data, private data, logs, or large generated artifacts.
```

## Expected Output

- Concise orientation summary.
- Relevant source pointers.
- Suggested validation commands.
- Assumptions or unknowns.
