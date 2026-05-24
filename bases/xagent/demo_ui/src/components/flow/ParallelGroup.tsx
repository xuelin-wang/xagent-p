import type { StepAuditEntry } from '../../types/agent_flow'
import { StepNode } from './StepNode'

interface SubagentEntry {
  name: string
  auditStep: StepAuditEntry | null
}

interface ParallelGroupProps {
  subagents: SubagentEntry[]
  onSelectStep: (step: StepAuditEntry) => void
}

export function ParallelGroup({ subagents, onSelectStep }: ParallelGroupProps) {
  if (subagents.length === 0) {
    return (
      <div className="rounded-lg border-2 border-dashed border-gray-600 bg-gray-800/50 px-3 py-2 text-xs text-gray-500">
        no subagents
      </div>
    )
  }

  return (
    <div className="rounded-lg border-2 border-dashed border-gray-600 bg-gray-800/50 px-3 py-2">
      <div className="text-xs text-gray-500 mb-2">parallel</div>
      <div className="flex gap-2 flex-wrap">
        {subagents.map((sa) => (
          <StepNode
            key={sa.name}
            stepName={`subagent:${sa.name}`}
            stepType="subagent"
            auditStep={sa.auditStep}
            onSelectStep={onSelectStep}
          />
        ))}
      </div>
    </div>
  )
}
