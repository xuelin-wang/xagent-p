# Refresh Project State

Use this when `mementum/state.md` may no longer reflect current direction, focus, blockers, next steps, or recent decisions.

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
