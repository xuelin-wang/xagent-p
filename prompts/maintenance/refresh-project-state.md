---
name: refresh-project-state
version: 1
status: active
purpose: Refresh mementum/state.md from current repository facts.
applies_to: [codex, claude]
last_updated: 2026-05-11
---

# Refresh Project State

## When to Use

Use this when `mementum/state.md` may no longer reflect current direction, focus, blockers, next steps, or recent decisions.

## Prompt

```text
Refresh `mementum/state.md` from current repository context.

Inspect:
1. `AGENTS.md`
2. `CLAUDE.md`
3. Current `mementum/state.md`
4. Relevant `mementum/knowledge/` pages
5. Recent changelogs, source files, tests, scripts, config, and docs related to the changed work

Update only these state-oriented sections when warranted:
- Current Direction
- Current Focus
- Next Steps
- Blockers / Unknowns
- Recent Decisions
- Source Pointers

Rules:
1. Keep the file concise and current.
2. Treat repo files as source of truth.
3. Do not duplicate the codebase map or detailed knowledge pages.
4. Mark uncertain items as unknown or to be verified.
5. Do not store secrets, runtime data, private data, raw logs, or large generated artifacts.

After editing, report:
1. What state changed.
2. Source pointers used.
3. Assumptions or to-be-verified items.
4. Confirmation that no sensitive/runtime data was added.
```

## Expected Output

- Updated `mementum/state.md`.
- Concise summary of changed state.
- Source pointers and uncertainties.
