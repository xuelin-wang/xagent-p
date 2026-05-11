Codex uses AGENTS.md as checked-in project guidance; OpenAI says required team guidance should live in AGENTS.md or checked-in docs, while Codex Memories are only a local recall layer. Claude Code uses CLAUDE.md for project-specific instructions and supports project memory/context files; Claude docs also recommend using checked-in project files for shared team behavior rather than only local memory.

Copy the document below into a Claude Code or Codex task.

# Task: Add a Mementum-Style Project Memory Layer to This Repository

## Goal

Add a lightweight, Git-backed project memory system to this repository.

This memory layer is for engineering/project knowledge only. It should help future AI coding agents and human contributors understand:

- current project state
- architectural decisions
- design rationale
- implementation conventions
- known pitfalls
- open questions
- durable lessons learned during development

This memory layer must be application-neutral. Do not add domain-specific folder names or assume what the application is about.

The system should work with both:

- Codex, via `AGENTS.md`
- Claude Code, via `CLAUDE.md`

## High-Level Design

Create a repo-local `mementum/` directory with three main layers:

```text
mementum/
  state.md
  memories/
  knowledge/

Meaning:

state.md
  Current project state, current direction, next steps, blockers, and recent decisions.

memories/
  Small durable observations. One insight per file. Short, specific, searchable.

knowledge/
  Longer synthesized project knowledge: architecture notes, design decisions, policies,
  conventions, workflows, and open design questions.

This is not runtime application memory.

Do not store sensitive data, secrets, user data, production data, customer data, or application runtime records in mementum/.

Required Files to Create

Create this structure:

AGENTS.md
CLAUDE.md

mementum/
  README.md
  state.md

  memories/
    README.md
    do-not-store-runtime-data-in-project-memory.md
    project-memory-is-engineering-context.md
    update-memory-when-lessons-become-durable.md

  knowledge/
    README.md
    project-memory-policy.md
    codebase-map.md
    architecture-decisions.md
    implementation-invariants.md
    development-workflows.md
    testing-and-evaluation.md
    security-and-data-boundaries.md
    open-questions.md

  templates/
    memory.md
    knowledge.md
    decision.md

If any of these files already exist, preserve existing content and update them carefully instead of overwriting.

Root AGENTS.md

Create or update AGENTS.md at the repository root.

Content:

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
Root CLAUDE.md

Create or update CLAUDE.md at the repository root.

Content:

@AGENTS.md

# Claude Code Notes

Use `AGENTS.md` as the shared project instruction source.

For large or ambiguous changes:

1. Read `mementum/state.md`.
2. Search `mementum/knowledge/`.
3. Search `mementum/memories/`.
4. Make a concise plan before editing.
5. Update or propose project memory changes when durable lessons are learned.

Keep project memory concise, accurate, and safe to commit.
mementum/README.md

Create:

# Mementum Project Memory

This directory contains repo-local project memory.

It is intended to help future AI coding agents and human contributors understand the project without rediscovering the same context repeatedly.

## Structure

```text
mementum/
  state.md       # current state, next steps, blockers, recent decisions
  memories/      # short durable observations, one insight per file
  knowledge/     # longer synthesized project knowledge
  templates/     # templates for new memory and knowledge files
What Belongs Here

Use this directory for durable engineering/project context:

architectural decisions
design rationale
implementation conventions
known pitfalls
recurring workflows
testing strategy
security and data boundaries
open questions
lessons learned
What Does Not Belong Here

Do not store:

secrets
credentials
tokens
private user data
customer data
production data
raw logs
large artifacts
runtime application records
temporary scratch notes
How Agents Should Use This

Before major design or implementation work:

Read mementum/state.md.
Search mementum/knowledge/ for relevant background.
Search mementum/memories/ for known pitfalls.
Inspect the actual code.
Implement the smallest safe change.
Propose memory updates when durable lessons are learned.
Maintenance Rule

Project memory should stay concise, useful, and current.

If a memory becomes outdated, either update it, supersede it, or move the corrected understanding into a knowledge page.


## `mementum/state.md`

Create:

```markdown
# Project State

## Current Direction

- This repository uses a Mementum-style project memory layer under `mementum/`.
- Project memory is for engineering context, not runtime application data.
- `AGENTS.md` is the shared instruction file for Codex and other agents.
- `CLAUDE.md` imports `AGENTS.md` for Claude Code.

## Current Focus

- Establish project memory conventions.
- Make future AI coding sessions easier to orient.
- Preserve design rationale and durable lessons in Git.

## Next Steps

- Fill in `mementum/knowledge/codebase-map.md` after inspecting the repository.
- Fill in `mementum/knowledge/architecture-decisions.md` as decisions are made.
- Fill in `mementum/knowledge/implementation-invariants.md` with rules that must remain true.
- Add short memory files under `mementum/memories/` when durable lessons are learned.

## Blockers / Unknowns

- Codebase-specific architecture has not yet been summarized.
- Build/test commands may still need to be documented.
- Project-specific security and data boundaries may still need to be filled in.

## Recent Decisions

- Project memory will live in this repository under `mementum/`.
- Project memory will be application-neutral.
- Runtime application memory/data must not be stored in `mementum/`.
- `AGENTS.md` and `CLAUDE.md` will instruct agents to consult project memory before major work.
mementum/memories/README.md

Create:

# Memories

This directory contains short durable observations.

Each memory should be:

- one insight
- short and specific
- useful to future contributors or AI agents
- safe to commit
- easy to search with grep

Prefer fewer, higher-quality memories over many noisy notes.

## Suggested Format

```markdown
# Short Title

Symbol: 📌 | 💡 | ❌ | ✅ | 🔁 | ⚠️

One concise explanation of the lesson.

Why it matters:
- ...

Future implication:
- ...
Suggested Symbols
📌 decision
💡 insight
❌ mistake / pitfall
✅ validated pattern
🔁 recurring pattern
⚠️ caution

## Initial Memory: `do-not-store-runtime-data-in-project-memory.md`

Create:

```markdown
# Do Not Store Runtime Data in Project Memory

Symbol: ⚠️

`mementum/` is for engineering/project context only.

Do not store runtime application records, raw logs, user data, customer data, production data, secrets, credentials, or large generated artifacts here.

Why it matters:
- Project memory is committed to Git.
- Git history is durable and hard to fully erase.
- Runtime data often has privacy, retention, and access-control requirements.

Future implication:
- If data belongs to the running application, store it in the appropriate runtime datastore, not in `mementum/`.
Initial Memory: project-memory-is-engineering-context.md

Create:

# Project Memory Is Engineering Context

Symbol: 📌

Project memory exists to help future engineering sessions start with better context.

It should capture durable knowledge that is not obvious from code alone: design rationale, implementation conventions, known pitfalls, and current project direction.

Why it matters:
- AI agents often restart without prior conversation context.
- Human contributors may not know why earlier decisions were made.
- Project memory reduces repeated rediscovery.

Future implication:
- Add memory only when it will likely help a future design or implementation session.
Initial Memory: update-memory-when-lessons-become-durable.md

Create:

# Update Memory When Lessons Become Durable

Symbol: 🔁

When a lesson is likely to matter again, add or update project memory.

Good examples:
- a design decision was made
- a repeated mistake was found
- a convention became important
- an implementation strategy was validated
- an open question was resolved

Avoid:
- temporary notes
- obvious facts
- speculative conclusions
- sensitive data
- routine edit summaries

Future implication:
- At the end of substantial work, consider whether `mementum/` should be updated.
mementum/knowledge/README.md

Create:

# Knowledge

This directory contains synthesized project knowledge.

Knowledge pages are longer-lived than memories and should explain design rationale, architecture, workflows, conventions, and open questions.

Use knowledge pages when several memories or discussions have converged into a stable understanding.

## Suggested Frontmatter

```yaml
---
title: Page Title
status: draft | active | superseded
category: architecture | design | workflow | policy | testing | security | open-question
tags: []
related: []
---
Maintenance
Keep pages concise.
Prefer clear decisions and implications.
Mark outdated pages as superseded instead of silently leaving stale guidance.
Link related pages when useful.

## `mementum/knowledge/project-memory-policy.md`

Create:

```markdown
---
title: Project Memory Policy
status: active
category: policy
tags: [memory, agents, documentation]
related:
  - codebase-map
  - implementation-invariants
---

# Project Memory Policy

## Purpose

Project memory helps future AI coding agents and human contributors understand this repository.

It captures durable engineering context that is not obvious from code alone.

## Project Memory Is For

- architecture decisions
- design rationale
- implementation conventions
- known mistakes and gotchas
- recurring workflows
- testing and evaluation strategy
- security and data boundaries
- current project state
- open design questions

## Project Memory Is Not For

- runtime application data
- secrets
- credentials
- private data
- production data
- raw logs
- large generated artifacts
- temporary scratch notes

## Memory Quality Bar

A memory should be added only if it is:

- durable
- safe to commit
- project-relevant
- likely to help future work
- not obvious from code alone

## Agent Workflow

Before major work:

1. Read `mementum/state.md`.
2. Search `mementum/knowledge/`.
3. Search `mementum/memories/`.
4. Inspect the code.
5. Make a minimal, testable change.
6. Propose memory updates if durable lessons were learned.

## Human Review

Project memory is part of the repository.

Changes to project memory should be reviewed like other documentation changes.
mementum/knowledge/codebase-map.md

Create:

---
title: Codebase Map
status: draft
category: architecture
tags: [repo, orientation]
related:
  - development-workflows
---

# Codebase Map

This page should summarize the repository structure after the codebase is inspected.

## Top-Level Structure

To be filled in.

Suggested format:

```text
path/
  purpose
Main Runtime Flow

To be filled in.

Describe the main flow through the application in 5-10 steps.

Important Modules

To be filled in.

For each important module:

module/path
  responsibility
  important dependencies
  common change points
Generated or External Files

To be filled in.

Document files or directories that agents should not edit manually.

Notes for Future Agents

To be filled in.

Add codebase-specific orientation notes that are useful before implementation work.


## `mementum/knowledge/architecture-decisions.md`

Create:

```markdown
---
title: Architecture Decisions
status: draft
category: architecture
tags: [decisions, rationale]
related:
  - implementation-invariants
  - open-questions
---

# Architecture Decisions

Record important architecture decisions here.

Use this page for decisions that affect multiple files, modules, services, or future implementation direction.

## Decision Template

```markdown
## YYYY-MM-DD — Decision Title

Status: proposed | accepted | superseded

Decision:
- ...

Context:
- ...

Alternatives considered:
- ...

Rationale:
- ...

Implications:
- ...

Follow-up:
- ...
Decisions

No project-specific decisions have been recorded yet.


## `mementum/knowledge/implementation-invariants.md`

Create:

```markdown
---
title: Implementation Invariants
status: draft
category: design
tags: [invariants, implementation]
related:
  - architecture-decisions
  - testing-and-evaluation
---

# Implementation Invariants

This page records rules that should remain true as the code evolves.

Invariants are stronger than preferences. If an implementation would violate an invariant, the design should be reconsidered.

## Current Invariants

- Project memory under `mementum/` must not contain secrets or runtime application data.
- Major design changes should preserve or update relevant project memory.
- Tests should be added or updated when behavior changes.
- Existing behavior should be preserved unless explicitly changed.
- Generated files should not be manually edited unless the generation process is also updated.

## Add Project-Specific Invariants Here

To be filled in as the codebase matures.
mementum/knowledge/development-workflows.md

Create:

---
title: Development Workflows
status: draft
category: workflow
tags: [development, agents, process]
related:
  - codebase-map
  - testing-and-evaluation
---

# Development Workflows

This page records common development workflows for this repository.

## Before Major Work

1. Read `mementum/state.md`.
2. Search relevant project memory.
3. Inspect the code.
4. Identify tests or validation commands.
5. Make a concise plan.
6. Implement the smallest safe change.
7. Run relevant validation.
8. Update project memory if a durable lesson was learned.

## Build Commands

To be filled in.

```bash
# example
Test Commands

To be filled in.

# example
Lint / Format Commands

To be filled in.

# example
Common Workflows

To be filled in after inspecting the repository.

Examples:

add a feature
fix a bug
update configuration
update generated code
change API contracts
update documentation

## `mementum/knowledge/testing-and-evaluation.md`

Create:

```markdown
---
title: Testing and Evaluation
status: draft
category: testing
tags: [tests, validation, evaluation]
related:
  - development-workflows
  - implementation-invariants
---

# Testing and Evaluation

This page records how changes should be validated.

## General Policy

- Add or update tests when behavior changes.
- Prefer focused tests for the changed behavior.
- Do not rely only on manual inspection for logic changes.
- If a change cannot be tested directly, document the reason and provide another validation method.

## Test Types

To be filled in.

Suggested sections:
- unit tests
- integration tests
- end-to-end tests
- static checks
- linting
- type checking
- evaluation datasets
- manual validation

## Required Validation Commands

To be filled in after inspecting the repository.

```bash
# example
Known Testing Gaps

To be filled in.


## `mementum/knowledge/security-and-data-boundaries.md`

Create:

```markdown
---
title: Security and Data Boundaries
status: draft
category: security
tags: [security, data, privacy]
related:
  - project-memory-policy
---

# Security and Data Boundaries

This page records what must not be stored, logged, exposed, or committed.

## Never Commit

- secrets
- credentials
- API keys
- tokens
- private keys
- production data
- customer data
- private user data
- raw logs containing sensitive data
- local environment files with secrets

## Project Memory Boundary

`mementum/` is safe-to-commit engineering context only.

Do not store runtime data or sensitive data in project memory.

## Environment and Configuration

To be filled in.

Document how secrets and environment-specific settings should be handled in this repository.

## Logging and Tracing

To be filled in.

Document project-specific rules for logs, traces, and large payloads.
mementum/knowledge/open-questions.md

Create:

---
title: Open Questions
status: active
category: open-question
tags: [questions, design]
related:
  - architecture-decisions
---

# Open Questions

Use this page to track unresolved design questions.

When an open question is resolved:

1. Move the decision to `architecture-decisions.md` or the relevant knowledge page.
2. Update this page to remove or mark the question resolved.
3. Add a short memory if the lesson is likely to recur.

## Questions

No project-specific open questions have been recorded yet.

## Template

```markdown
## Question Title

Status: open | resolved | deferred

Question:
- ...

Context:
- ...

Options:
- ...

Current leaning:
- ...

Decision needed by:
- ...

## Templates

Create `mementum/templates/memory.md`:

```markdown
# Short Memory Title

Symbol: 📌 | 💡 | ❌ | ✅ | 🔁 | ⚠️

Short statement of the durable lesson.

Why it matters:
- ...

Future implication:
- ...

Related:
- ...

Create mementum/templates/knowledge.md:

---
title: Page Title
status: draft
category: architecture | design | workflow | policy | testing | security | open-question
tags: []
related: []
---

# Page Title

## Summary

Brief summary.

## Context

Why this page exists.

## Details

Main content.

## Decisions / Rules

- ...

## Implications

- ...

## Related Files

- ...

Create mementum/templates/decision.md:

## YYYY-MM-DD — Decision Title

Status: proposed | accepted | superseded

Decision:
- ...

Context:
- ...

Alternatives considered:
- ...

Rationale:
- ...

Implications:
- ...

Follow-up:
- ...
Final Validation

After creating or updating the files:

Show the resulting file tree.
Summarize what was added.
Do not modify application code unless needed to create these documentation files.
Do not invent project-specific architecture details. Leave placeholders as To be filled in if the repository has not been inspected deeply enough.
Ensure no sensitive data was added.

My suggested first command to the agent would be:

```text
Apply this project-memory bootstrap exactly. Create the files if missing, preserve existing content if present, and do not add application-specific assumptions.