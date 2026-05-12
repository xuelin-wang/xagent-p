---
name: mementum-memory
description: Maintain this repository's Mementum project memory. Use when asked to check, update, refresh, prune, synthesize, audit, or compare project memory under mementum/ against the current codebase.
---

# Mementum Memory

Use this skill for project-memory work in this repository.

Project memory lives under `mementum/` and is for durable repository context:

- architecture decisions
- design rationale
- implementation conventions
- known mistakes and gotchas
- durable lessons learned
- current project state
- open design questions
- development workflows

Do not store secrets, credentials, personal data, customer data, production data, raw logs, runtime application records, large generated artifacts, or temporary scratch notes in project memory.

## Core Workflow

1. Read `AGENTS.md`.
2. Read `mementum/state.md`.
3. Search `mementum/knowledge/` for relevant design, workflow, testing, security, and open-question context.
4. Search `mementum/memories/` for known pitfalls or durable lessons.
5. Inspect the current repository files needed to verify memory against code.
6. Update memory only when a durable fact, decision, convention, workflow, lesson, or open question changed.
7. Keep edits concise and source-backed.
8. Report updated files, why the update was durable, source pointers used, and confirmation that no sensitive/runtime data was added.

## Choose a Workflow

- End-of-task memory decision: read `references/update-project-memory.md`.
- Refresh current project state: read `references/refresh-project-state.md`.
- Refresh broader project memory: read `references/refresh-project-memory.md`.
- Refresh the codebase map: read `references/refresh-codebase-map.md`.
- Synthesize repeated memories into knowledge: read `references/synthesize-memories.md`.
- Prune stale or unsafe memory: read `references/prune-stale-memory.md`.

Read only the reference needed for the user's request.

## Destination Rules

- Use `mementum/state.md` for current direction, current focus, blockers, next steps, recent decisions, and source pointers.
- Use `mementum/memories/` for one short durable lesson per file.
- Use `mementum/knowledge/` for synthesized design, workflow, testing, security, architecture, policy, or open-question context.
- Use changelogs for detailed change explanations, not durable project state.
- Use `skills/mementum-memory/` for this memory-maintenance workflow; do not duplicate these workflows under `prompts/maintenance/`.

## Quality Bar

Good memory updates have clear continuing value. Routine edit summaries, obvious facts, speculative notes, copied README content, and temporary task details should be left out.
