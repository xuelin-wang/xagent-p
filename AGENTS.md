# Agent Instructions

## Project Orientation

Before major design, refactoring, or implementation work:

1. Read `mementum/state.md`.
2. Search `mementum/knowledge/` for relevant design context.
3. Search `mementum/memories/` for known pitfalls or prior lessons.
4. Inspect the actual code before making changes.
5. Prefer small, testable changes over broad rewrites.

For trivial edits, reading all memory is not required. For architectural, cross-cutting, or ambiguous work, project memory should be consulted first.

## Project Memory

This repository uses a Mementum-style project memory layer under `mementum/`.

Project memory is for:

- architecture decisions
- design rationale
- implementation conventions
- known mistakes and gotchas
- durable lessons learned
- current project state
- open design questions
- development workflows

Project memory is not for:

- secrets
- credentials
- personal data
- customer data
- production data
- raw logs
- runtime application records
- large generated artifacts
- temporary scratch notes

## Memory Update Rule

When a durable project lesson is learned, propose an update to `mementum/`.

Good candidates:

- a design decision was made
- a previous assumption was corrected
- a bug revealed a reusable lesson
- a convention became important
- a workflow should be repeated
- an implementation pitfall should be avoided
- an open question was resolved

Do not add memory for routine edits, temporary details, obvious facts, or sensitive data.

## Reusable Workflow Prompts

Reusable prompts for common coding-agent workflows live under `prompts/`.

Project-memory maintenance workflows live under the repo-local `skills/mementum-memory/` skill.

Use them when appropriate:

- `prompts/workflows/orient-repo.md`
- `prompts/workflows/implement-feature.md`
- `prompts/workflows/fix-bug.md`
- `prompts/workflows/refactor-code.md`
- `prompts/workflows/generate-changelog.md`
- `prompts/reviews/review-current-branch.md`
- `prompts/reviews/review-pr-risk.md`
- `prompts/reviews/compare-branches.md`
- `prompts/reviews/security-review.md`
- `prompts/reviews/test-coverage-review.md`

If a workflow prompt proves useful and reusable, update it in `prompts/` rather than leaving it only in chat history.

If a project-memory maintenance workflow changes, update `skills/mementum-memory/` rather than duplicating it under `prompts/`.

## Implementation Principles

- Understand existing code before changing it.
- Preserve existing behavior unless explicitly asked to change it.
- Keep changes minimal and focused.
- Add or update tests when behavior changes.
- Separate facts from assumptions.
- Record important design rationale in project memory.
- Do not treat project memory as a substitute for tests, schemas, or enforceable configuration.

## If Instructions Conflict

Follow this priority order:

1. Explicit user request
2. Safety/security constraints
3. More specific repository instructions
4. `mementum/` project memory
5. General best practices

If conflict remains, explain the conflict and choose the safest minimal path.
