# Live Provider Tests Are Opt In

Symbol: ✅

Normal pytest runs exclude live provider tests through the `require_env` marker.

Why it matters:
- Live tests need real credentials, network access, provider availability, and may cost money.
- The default suite should stay deterministic for routine development.

Source pointers:
- `pyproject.toml`
- `test/integration/test_openai_live.py`
- `test/integration/test_anthropic_live.py`

Future implication:
- Use `-m require_env` explicitly when validating real OpenAI or Anthropic behavior.
