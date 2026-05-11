---
title: Open Questions
status: active
category: open-question
tags: [questions, design]
related:
  - architecture-decisions
---

# Open Questions

## Purpose

Track unresolved questions that are useful before implementation work.

## Questions

## CI Location

Status: open

Question:
- Is CI configured outside this repository, or has it not been added yet?

Context:
- No `.github/` workflow files were found in the checkout.

Source pointers:
- `.github/` search result from repository inspection

## Lint and Type Checking

Status: open

Question:
- Should this repo adopt dedicated linting and type-checking commands?

Context:
- `pyproject.toml` configures pytest but no lint/type-check tool configuration was found.

Source pointers:
- `pyproject.toml`

## Logging and Tracing Policy

Status: open

Question:
- What logging/tracing stack and redaction policy should the application use?

Context:
- `README.md` lists logs, Phoenix tracing, OpenTelemetry, Signoz, and GCP log collection as TODOs.
- LLM design guidance says not to log sensitive provider payloads by default.

Source pointers:
- `README.md`
- `changelogs/20250509-llm-api-layer-design.txt`
