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

## Real Tool Execution in Subagent Path

Status: open

Question:
- Should `LLMFlowSubagent` be replaced with the full planner→validate→execute→merge pipeline, and what is the right sequencing?

Context:
- `ToolCallStep`, `build_execute_tools_step`, `ValidatedToolCall`, and `ToolResult` are all implemented and durable.
- `LLMFlowSubagent` currently bypasses this pipeline; it does one monolithic LLM call that acts as planner, tool executor, and summarizer combined.
- Wiring real tools in requires concrete `ToolExecutor` implementations and connecting the planner's `PlanSubagentSelection` to validated tool calls.

Source pointers:
- `components/xagent/agent_flow/tools.py`
- `components/xagent/agent_flow/tool_registry.py`
- `components/xagent/agent_flow/subagents.py`

## Evaluation Quality Metrics

Status: open

Question:
- What ground-truth datasets or LLM judge approach should back content-quality scoring in `evaluation.py`?

Context:
- `evaluation.py` currently produces only structural metrics (counts, flags, decision sequences, failure modes).
- Answer quality, grounding, tool selection quality, and unsupported-claim detection all require either reference answers or LLM judges.
- The evaluator interface (`evaluate_state`, `evaluate_run`) is in place; scoring logic is the gap.

Source pointers:
- `components/xagent/agent_flow/evaluation.py`
- `mementum/knowledge/replay-resume-agent-system-design.md` (Section 14)

## Logging and Tracing Policy

Status: open

Question:
- What logging/tracing stack and redaction policy should the application use?

Context:
- `README.md` lists logs, Phoenix tracing, OpenTelemetry, Signoz, and GCP log collection as TODOs.
- LLM design guidance says not to log sensitive provider payloads by default.

Source pointers:
- `README.md`
