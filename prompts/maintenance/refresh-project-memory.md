---
name: refresh-project-memory
version: 1
status: active
purpose: Refresh current project memory from repo files without inventing facts.
applies_to: [codex, claude]
last_updated: 2026-05-11
---

# Refresh Project Memory

## When to Use

Use this when `mementum/` may be stale after meaningful repository changes.

## Prompt

```text
Refresh project memory from current repository files.

Goal:
Keep `mementum/` concise, accurate, and useful for future implementation work.

Inspect:
1. `AGENTS.md` and `CLAUDE.md`
2. `mementum/state.md`
3. Existing `mementum/knowledge/` pages
4. Existing `mementum/memories/`
5. Relevant source, tests, docs, scripts, deployment config, and changelogs

Update only when repo-derived facts or durable lessons changed.

Prefer:
- updating `mementum/state.md` for current direction, focus, next steps, blockers, and recent decisions
- updating knowledge pages for stable synthesized understanding
- adding short memory files for one durable lesson each

Avoid:
- redundant repo summaries
- listing every file
- copying README/config content
- inventing decisions
- routine edit summaries
- secrets, runtime data, private data, raw logs, or large generated artifacts

For uncertain items, mark them as "To be verified" or put them in `mementum/knowledge/open-questions.md`.

After editing, show:
1. Updated files.
2. What changed and why.
3. Assumptions or to-be-verified items.
4. Confirmation that no sensitive/runtime data was added.
```

## Expected Output

- Concise memory updates.
- Source pointers for repo-derived facts.
- Clear list of to-be-verified items.
