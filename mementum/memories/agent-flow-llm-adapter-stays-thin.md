# Agent-Flow LLM Adapter Stays Thin

Symbol: 📌

The agent-flow LLM adapter should stay as a narrow bridge to the existing `LLMProvider` protocol, with planner, subagent, and summary executors built on top of it rather than creating a separate agent-specific LLM stack.

Why it matters:
- The repo already has provider contracts for text and structured generation.
- A thin adapter keeps agent-flow aligned with the shared provider layer.
- It avoids duplicating provider selection, request serialization, and structured-output handling.

Source pointers:
- `components/xagent/agent_flow/llm_adapter.py`
- `components/xagent/agent_flow/service.py`
- `components/xagent/llm_registry/provider_protocol.py`

Future implication:
- Add new agent-specific behavior in executors or runtime code first; only extend the adapter when the shared provider protocol is genuinely missing something.

