# Agent-Flow Execution Policy Inherits Through Step Tree

Symbol: ✅

Agent-flow execution policy belongs to the durable step tree, not to ad hoc executor calls.

Why it matters:
- Top-level steps should start from `agent_flow.execution_policy`.
- Composite child steps inherit their parent policy before applying step-type or local overrides.
- Timeout/deadline behavior stays consistent for planner, subagent, summary, and tool-call work.

Source pointers:
- `components/xagent/agent_flow/config.py`
- `components/xagent/agent_flow/steps.py`
- `components/xagent/agent_flow/step_runner.py`
- `components/xagent/agent_flow/tools.py`
- `test/components/xagent/agent_flow/test_steps.py`
- `test/components/xagent/agent_flow/test_step_runner.py`

Future implication:
- New specialized steps or tool pipelines should enter through `RuntimeContext`/`StepRunner` so timeout, deadline, and retry policy are inherited and enforced uniformly.
