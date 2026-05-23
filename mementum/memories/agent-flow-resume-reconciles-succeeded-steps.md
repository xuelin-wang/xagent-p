# Agent-Flow Resume Reconciles Succeeded Steps

Symbol: ⚠️

When resuming a durable agent-flow run, reconcile succeeded step records back into the in-memory iteration state before rerunning anything.

Why it matters:
- A checkpoint alone may lag behind completed step rows after a crash.
- Step-level success is the reliable source for skipping already-completed planner, subagent, or summary work.
- This prevents duplicate work and makes resume safe after partial completion.

Source pointers:
- `components/xagent/agent_flow/runtime.py`
- `components/xagent/agent_persistence/repositories.py`
- `test/components/xagent/agent_flow/test_runtime.py`

Future implication:
- Any later Postgres implementation must preserve step-level reconciliation, not just checkpoint replay.

Synthesis:
- Synthesized into `mementum/knowledge/replay-resume-agent-system-design.md` and `mementum/knowledge/replay-resume-agent-implementation-plan.md`.
- The future design preserves this lesson through append-only `step_succeeded` events, checkpoint-aligned step completion, and durable child `tool_call` steps rather than checkpoint-only resume.
