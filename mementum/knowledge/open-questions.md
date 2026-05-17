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

## Logging and Tracing Policy

Status: open

Question:
- What logging/tracing stack and redaction policy should the application use?

Context:
- `README.md` lists logs, Phoenix tracing, OpenTelemetry, Signoz, and GCP log collection as TODOs.
- LLM design guidance says not to log sensitive provider payloads by default.

Source pointers:
- `README.md`
