# Coding Agent Prompt Library Changes

## Feature Summary

This branch introduces a reusable `prompts/` library for common coding-agent workflows, reviews, and project-memory maintenance. It updates root agent guidance so future agents know to use these prompts, and records the design decision that reusable workflow prompts belong outside `mementum/` project memory.

No application code or runtime behavior changes are introduced.

## Rationale

The branch separates reusable agent instructions from durable project memory. `prompts/` now holds task-oriented instructions that can evolve through repeated use, while `mementum/` remains focused on repository state, decisions, conventions, and lessons. This should make agent workflows easier to reuse without turning project memory into a prompt catalog.

## Reviewer Focus

- Confirm the prompt library structure is broad enough for current recurring workflows without becoming too granular.
- Check that `AGENTS.md`, `CLAUDE.md`, and `mementum/` now agree on the boundary between reusable prompts and project memory.
- Review prompt text for overreach: prompts should guide agents, not silently change repository policy or validation expectations beyond existing instructions.
- Note: `.swp` is an untracked editor artifact in the working tree and is not part of the intended branch content.

## File-by-File Notes

### `AGENTS.md`

Adds a "Reusable Workflow Prompts" section listing the prompt files agents should use when the task matches a standard workflow. The important behavior is instructional: agents are now expected to look in `prompts/` before relying on ad hoc chat instructions for repeated workflows.

### `CLAUDE.md`

Mirrors the new prompt-library guidance for Claude Code while keeping `AGENTS.md` as the shared source of truth. Reviewers should check that this remains a short adapter rather than a divergent instruction set.

### `changelogs/prompt.txt`

Refines the changelog-generation prompt from exhaustive line-by-line reporting toward concise, reviewer-focused summaries. This changes the intended style of future changelogs, not application behavior.

### `mementum/knowledge/architecture-decisions.md`

Adds the accepted decision to keep reusable prompts in `prompts/` and project memory in `mementum/`. This is the durable rationale that backs the new directory and root-agent instructions.

### `mementum/memories/reusable-prompts-live-outside-project-memory.md`

Adds a short reusable lesson with the same boundary in memory form. Reviewers should decide whether keeping both this memory and the architecture decision is useful, or whether one is redundant.

### `prompts/README.md`

Defines the new prompt library structure, usage expectations, and maintenance rules. This file is the main orientation point for future contributors editing prompts.

### `prompts/templates/prompt-template.md`

Provides front matter and section conventions for future prompts. The review point is whether the metadata fields are enough to keep prompts discoverable and maintainable without adding process burden.

### `prompts/workflows/orient-repo.md`

Codifies the repository-orientation workflow: read agent guidance, consult project memory, inspect relevant code, and summarize assumptions before editing. This aligns with existing repo instructions.

### `prompts/workflows/implement-feature.md`

Guides feature work through context gathering, scoped implementation, focused tests, validation, and project-memory hygiene. Reviewers should check that it does not encourage memory updates for routine feature work.

### `prompts/workflows/fix-bug.md`

Captures the bug-fix workflow: reproduce or localize, make a minimal fix, add regression coverage where practical, and update memory only for durable lessons.

### `prompts/workflows/refactor-code.md`

Frames refactoring as behavior-preserving work with scoped validation. The useful constraint is that it discourages unrelated cleanup and broad rewrites.

### `prompts/workflows/generate-changelog.md`

Adds a reusable prompt for branch changelog generation. It currently asks for a detailed report, while `changelogs/prompt.txt` now asks for concise reviewer-focused output; reviewers should reconcile that style difference if both prompts are intended to stay aligned.

### `prompts/reviews/review-current-branch.md`

Creates a general branch-review prompt focused on bugs, regressions, missing tests, data risks, unrelated artifacts, and stale memory. It preserves the existing review convention of findings first.

### `prompts/reviews/review-pr-risk.md`

Adds a merge-risk review prompt that looks beyond code correctness into rollout, compatibility, validation, and data-handling concerns.

### `prompts/reviews/compare-branches.md`

Adds a branch-comparison prompt that explicitly includes staged, unstaged, and untracked local files. This matters for this repo because work may exist before a commit is made.

### `prompts/reviews/security-review.md`

Adds a security and data-boundary review prompt. It is intentionally broad for changes that touch secrets, provider payloads, deployment files, external services, logging, or project memory.

### `prompts/reviews/test-coverage-review.md`

Adds a validation-focused review prompt for assessing whether changed behavior has adequate tests. It reinforces the existing project convention that live/provider tests remain opt-in.

### `prompts/maintenance/update-project-memory.md`

Adds an end-of-task decision prompt for whether project memory should change. This is the main guardrail against turning memory into routine task logs.

### `prompts/maintenance/refresh-project-state.md`

Adds a prompt for keeping `mementum/state.md` current without expanding it into a full codebase map.

### `prompts/maintenance/refresh-project-memory.md`

Adds a broader memory-refresh prompt that requires repo-derived facts and discourages speculative or sensitive content.

### `prompts/maintenance/refresh-codebase-map.md`

Adds a prompt for updating the codebase map after structural changes. It keeps the scope at high-value orientation facts rather than enumerating every file.

### `prompts/maintenance/synthesize-memories.md`

Adds a prompt for consolidating repeated short memories into longer-lived knowledge pages while preserving source pointers.

### `prompts/maintenance/prune-stale-memory.md`

Adds a prompt for finding stale, misleading, duplicated, or unsafe memory and correcting it against current repository facts.
