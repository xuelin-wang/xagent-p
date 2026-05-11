# Provider Mutations Are Not Auto-Retried

Symbol: ⚠️

LLM provider operations that create or alter provider resources are intentionally sent once by default.

Why it matters:
- Retrying uploads or native batch creation after a lost response can duplicate provider resources.
- Retrying deletes can leave ambiguous state.

Source pointers:
- `changelogs/20250509-llm-api-layer-changes.md`
- `components/xagent/llm_provider_openai/provider.py`
- `components/xagent/llm_provider_anthropic/provider.py`

Future implication:
- Add caller-owned idempotency or deduplication before changing mutation retry behavior.
