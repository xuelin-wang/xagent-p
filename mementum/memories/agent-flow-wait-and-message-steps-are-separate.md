# Wait and Message Are Separate Steps

Symbol: ✅

Pause/resume in agent flow should be represented by a durable `WaitStep`,
while the inbound message that resumes execution should be recorded as a
separate durable `MessageInputStep`.

Why it matters:
- The audit trail stays explicit: pause point, resumed message, then normal
  execution.
- Resume logic can stay conversation-scoped without hiding message ingestion
  inside the wait step.

Future implication:
- New pause/resume flows should preserve the `WaitStep -> MessageInputStep`
  audit shape instead of collapsing both concerns into one step.
