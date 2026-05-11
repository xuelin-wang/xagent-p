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
