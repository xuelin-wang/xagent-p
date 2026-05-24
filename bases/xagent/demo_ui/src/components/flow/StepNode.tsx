import type { StepAuditEntry, StepStatus } from '../../types/agent_flow'
import { StatusBadge } from '../shared/StatusBadge'

interface StepNodeProps {
  stepName: string
  stepType: 'planner' | 'subagent' | 'summary' | 'tool_call'
  auditStep: StepAuditEntry | null
  decisionLabel?: string
  onSelectStep: (step: StepAuditEntry) => void
}

const borderColor: Record<StepStatus, string> = {
  pending: 'border-gray-600',
  running: 'border-amber-500',
  waiting: 'border-purple-500',
  succeeded: 'border-green-500',
  failed: 'border-red-500',
  skipped: 'border-slate-500',
}

const typeIcon: Record<string, string> = {
  planner: '🗺',
  subagent: '🔍',
  summary: '📋',
  tool_call: '⚙',
}

function shortName(stepName: string): string {
  if (stepName === 'planner') return 'Planner'
  if (stepName === 'summary') return 'Summary'
  if (stepName.startsWith('subagent:')) return stepName.slice('subagent:'.length)
  return stepName
}

export function StepNode({
  stepName,
  stepType,
  auditStep,
  decisionLabel,
  onSelectStep,
}: StepNodeProps) {
  const status: StepStatus = auditStep?.status ?? 'pending'
  const border = borderColor[status]
  const isSkipped = status === 'skipped'
  const icon = typeIcon[stepType] ?? '•'

  function handleClick() {
    if (auditStep) onSelectStep(auditStep)
  }

  return (
    <div
      onClick={handleClick}
      className={`rounded-lg border-l-4 ${border} bg-gray-800 p-3 min-w-[120px] ${
        auditStep ? 'cursor-pointer hover:bg-gray-700' : 'cursor-default'
      } transition-colors`}
    >
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className="text-sm">{icon}</span>
        <span className="text-xs font-medium text-gray-200 truncate">
          {shortName(stepName)}
        </span>
      </div>

      <StatusBadge status={status} />

      {decisionLabel && (
        <span className="ml-1 inline-flex items-center rounded px-1.5 py-0.5 text-xs bg-gray-700 text-gray-300">
          {decisionLabel}
        </span>
      )}

      {auditStep && auditStep.attempt_count > 1 && (
        <div className="text-xs text-gray-500 mt-1">
          attempt {auditStep.attempt_count}
        </div>
      )}

      {isSkipped && (
        <div className="mt-1 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs bg-slate-700 text-slate-300">
          ↺ Replayed
        </div>
      )}
    </div>
  )
}
