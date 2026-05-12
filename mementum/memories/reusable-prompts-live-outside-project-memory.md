# Reusable Prompts Live Outside Project Memory

Symbol: 📌

Reusable coding-agent workflow prompts belong under `prompts/`, not inside `mementum/`.

Why it matters:
- `prompts/` contains task instructions that agents can reuse.
- `mementum/` contains durable project state, decisions, rationale, conventions, pitfalls, and lessons.
- Keeping the two separate prevents project memory from becoming a prompt library.

Source pointers:
- `prompts/README.md`
- `AGENTS.md`
- `mementum/knowledge/architecture-decisions.md`

Future implication:
- Improve reusable workflow instructions in `prompts/`; record durable lessons from prompt use in `mementum/` only when they meet the memory quality bar.
