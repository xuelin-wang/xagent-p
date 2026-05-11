# Preserve Loose Polylith Boundaries

Symbol: 📌

This repository builds the `xagent` namespace from `components/xagent` and `bases/xagent`; new shared code should follow that layout instead of adding a parallel `src/` tree.

Why it matters:
- Package/build config and tests are organized around loose Polylith bricks.
- Provider and shared LLM components rely on directional boundaries.

Source pointers:
- `workspace.toml`
- `pyproject.toml`
- `changelogs/20250509-llm-api-layer-design.txt`

Future implication:
- Add reusable implementation under `components/xagent/` and executable entry points under `bases/xagent/` unless the architecture is intentionally changed.
