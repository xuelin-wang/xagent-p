import type {
  AgentFlowState,
  RunAuditRecord,
  StepAuditEntry,
} from '../../types/agent_flow'
import { IterationBlock, getAuditStep } from './IterationBlock'
import { ResumePoint } from './ResumePoint'
import { WaitingNode } from './WaitingNode'
import { FinalResult } from './FinalResult'

interface FlowChartProps {
  state: AgentFlowState
  audit: RunAuditRecord | null
  onSelectStep: (step: StepAuditEntry) => void
}

function allSkipped(
  audit: RunAuditRecord | null,
  iterationNum: number
): boolean {
  if (!audit) return false
  const steps = audit.steps.filter((s) => s.iteration === iterationNum)
  if (steps.length === 0) return false
  return steps.every((s) => s.status === 'skipped')
}

function hasNonSkipped(
  audit: RunAuditRecord | null,
  iterationNum: number
): boolean {
  if (!audit) return false
  return audit.steps.some(
    (s) => s.iteration === iterationNum && s.status !== 'skipped'
  )
}

export function FlowChart({ state, audit, onSelectStep }: FlowChartProps) {
  if (state.iterations.length === 0) {
    return (
      <div className="flex flex-col items-center gap-4 p-6">
        <p className="text-sm text-gray-500">
          {state.status === 'running' || state.status === 'pending'
            ? 'Run in progress — waiting for first iteration…'
            : 'No iterations recorded.'}
        </p>
        {state.status === 'waiting_for_user' && (
          <WaitingNode request={state.pending_user_request} />
        )}
        <FinalResult state={state} />
      </div>
    )
  }

  const elements: React.ReactNode[] = []

  state.iterations.forEach((iter, i) => {
    if (i > 0) {
      const prevIter = state.iterations[i - 1]
      const prevAllSkipped = allSkipped(audit, prevIter.iteration)
      const currHasNonSkipped = hasNonSkipped(audit, iter.iteration)
      if (prevAllSkipped && currHasNonSkipped) {
        elements.push(<ResumePoint key={`resume-${i}`} />)
      }
    }
    elements.push(
      <IterationBlock
        key={iter.iteration}
        iteration={iter}
        audit={audit}
        onSelectStep={onSelectStep}
      />
    )
  })

  // Verify last planner step exists for "running in next iteration" hint
  // (no extra logic needed, WaitingNode and FinalResult handle terminal states)

  return (
    <div className="flex flex-col items-center gap-4 p-6">
      {elements}
      {state.status === 'waiting_for_user' && (
        <WaitingNode request={state.pending_user_request} />
      )}
      <FinalResult state={state} />
    </div>
  )
}

// Re-export helper for use in App
export { getAuditStep }
