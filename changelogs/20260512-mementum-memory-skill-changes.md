# Mementum Memory Skill Changes

## Feature Summary

This change moves project-memory maintenance workflows out of `prompts/maintenance/` and into a repo-local skill at `skills/mementum-memory/`.

The prompt library remains the home for general coding-agent workflows and review prompts. The new skill is the single source of truth for memory-specific operations such as updating project state, refreshing memory, pruning stale memory, synthesizing memories, and refreshing the codebase map.

## Rationale

Project-memory maintenance is a recurring operation that benefits from automatic skill triggering and shared workflow rules. Keeping these workflows in a skill avoids duplicating detailed maintenance prompts while preserving `mementum/` as durable project memory rather than a workflow library.

## File-by-File Notes

### `skills/mementum-memory/SKILL.md`

Defines the repo-local skill, trigger scope, shared memory rules, destination rules, and routing to workflow references. Reviewers should confirm the description is broad enough to trigger for common memory requests without overlapping unrelated prompt workflows.

### `skills/mementum-memory/references/*.md`

Contains the detailed maintenance workflows previously stored under `prompts/maintenance/`: update project memory, refresh state, refresh memory, refresh codebase map, synthesize memories, and prune stale memory. Keeping them as references keeps `SKILL.md` small while preserving one workflow per file.

### `prompts/maintenance/*.md`

Removed to eliminate duplicate workflow sources. Future memory-maintenance edits should happen under `skills/mementum-memory/`.

### `prompts/README.md`

Updates the prompt-library structure so it no longer advertises maintenance prompts. It now points project-memory maintenance readers to the repo-local skill.

### `README.md`

Adds setup commands for exposing the repo-local skill to Codex and Claude Code through each tool's project skill discovery directory, using symlinks so `skills/mementum-memory/` remains the source of truth.

### `AGENTS.md` and `CLAUDE.md`

Update agent guidance to distinguish general reusable prompts from memory-maintenance skill workflows.

### `mementum/state.md` and `mementum/knowledge/codebase-map.md`

Refresh orientation facts so future agents see `skills/mementum-memory/` as the memory-maintenance workflow location.

### `mementum/knowledge/architecture-decisions.md`

Refines the prior reusable-prompt decision: general workflow prompts stay in `prompts/`, while project-memory maintenance workflows belong in the `mementum-memory` skill.

### `mementum/memories/reusable-prompts-live-outside-project-memory.md`

Updates the short memory so it no longer implies every reusable workflow belongs under `prompts/`.
