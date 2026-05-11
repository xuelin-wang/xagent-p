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
```

## What Belongs Here

Use this directory for durable engineering/project context:

- architectural decisions
- design rationale
- implementation conventions
- known pitfalls
- recurring workflows
- testing strategy
- security and data boundaries
- open questions
- lessons learned

## What Does Not Belong Here

Do not store:

- secrets
- credentials
- tokens
- private user data
- customer data
- production data
- raw logs
- large artifacts
- runtime application records
- temporary scratch notes

## How Agents Should Use This

Before major design or implementation work:

1. Read `mementum/state.md`.
2. Search `mementum/knowledge/` for relevant background.
3. Search `mementum/memories/` for known pitfalls.
4. Inspect the actual code.
5. Implement the smallest safe change.
6. Propose memory updates when durable lessons are learned.

## Maintenance Rule

Project memory should stay concise, useful, and current.

If a memory becomes outdated, either update it, supersede it, or move the corrected understanding into a knowledge page.
