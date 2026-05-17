# Agent-Flow Executor Selection Follows Model Config

Symbol: ✅

Agent-flow service construction should choose fake or provider-backed planner, subagent, and summary executors from `AgentFlowAppConfig` model fields, keeping `fake` as the deterministic default.

Why it matters:
- Local runs stay deterministic without credentials.
- Provider-backed executors are enabled by config rather than code changes.
- The same runtime can serve fake, local, and real-provider workflows.

Source pointers:
- `components/xagent/agent_flow/service.py`
- `components/xagent/agent_flow/config.py`
- `test/components/xagent/agent_flow/test_service.py`

Future implication:
- When adding new executor types, keep the config-driven selection pattern so local defaults remain simple and testable.

