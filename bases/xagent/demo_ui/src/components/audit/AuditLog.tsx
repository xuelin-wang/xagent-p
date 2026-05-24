import { useRef } from 'react'
import type { RunAuditRecord, AgentFlowState } from '../../types/agent_flow'
import { AuditRow } from './AuditRow'

interface AuditLogProps {
  audit: RunAuditRecord | null
  state: AgentFlowState
}

export function AuditLog({ audit, state }: AuditLogProps) {
  const prevCountRef = useRef(0)
  const steps = audit?.steps ?? []
  const messages = audit?.conversation_messages ?? state.conversation_messages
  const currentCount = steps.length + messages.length
  const prevCount = prevCountRef.current
  prevCountRef.current = currentCount

  if (!audit || steps.length === 0) {
    return (
      <div className="p-6">
        <p className="text-xs text-gray-500">No step records yet.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col">
      <div className="sticky top-0 bg-gray-950 border-b border-gray-800 px-3 py-2 z-10">
        <span className="font-mono text-xs text-gray-500">
          Audit Log — append-only 🔒
        </span>
      </div>

      <div>
        {steps.map((step, i) => (
          <AuditRow
            key={step.step_id}
            step={step}
            isNew={i >= prevCount}
          />
        ))}
        {messages.map((evt, i) => (
          <AuditRow
            key={evt.message_id}
            messageEvent={evt}
            isNew={steps.length + i >= prevCount}
          />
        ))}
        {state.user_input_events.map((evt) => (
          <AuditRow
            key={`${evt.run_id}-${evt.request_id}`}
            inputEvent={evt}
            isNew={false}
          />
        ))}
      </div>
    </div>
  )
}
