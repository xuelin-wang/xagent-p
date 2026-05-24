import type { StepAuditEntry, UserInputEvent, StepStatus } from '../../types/agent_flow'
import { StatusBadge } from '../shared/StatusBadge'

interface AuditRowProps {
  step?: StepAuditEntry
  inputEvent?: UserInputEvent
  isNew: boolean
}

const statusBar: Record<StepStatus, string> = {
  pending: 'bg-gray-500',
  running: 'bg-amber-500',
  waiting: 'bg-purple-500',
  succeeded: 'bg-green-500',
  failed: 'bg-red-500',
  skipped: 'bg-slate-500',
}

function copyText(text: string) {
  void navigator.clipboard.writeText(text)
}

export function AuditRow({ step, inputEvent, isNew }: AuditRowProps) {
  const animClass = isNew ? 'animate-slide-up' : ''

  if (inputEvent) {
    return (
      <div
        className={`flex items-start gap-2 px-3 py-2 border-b border-gray-800 hover:bg-gray-800/40 ${animClass}`}
      >
        <div className="w-1 self-stretch rounded bg-purple-500 shrink-0" />
        <div className="flex-1 min-w-0">
          <span className="text-xs font-mono text-purple-400 mr-2">
            user_input
          </span>
          <span className="text-xs text-gray-300 truncate">
            {inputEvent.content.slice(0, 80)}
            {inputEvent.content.length > 80 ? '…' : ''}
          </span>
        </div>
      </div>
    )
  }

  if (!step) return null

  const bar = statusBar[step.status] ?? 'bg-gray-500'

  return (
    <div
      className={`flex items-start gap-2 px-3 py-2 border-b border-gray-800 hover:bg-gray-800/40 ${animClass}`}
    >
      <div className={`w-1 self-stretch rounded ${bar} shrink-0`} />
      <div className="flex-1 min-w-0 flex flex-wrap items-center gap-1.5">
        <span className="font-mono text-xs text-gray-200">{step.step_name}</span>
        <span className="text-xs text-gray-500">{step.step_type}</span>
        <StatusBadge status={step.status} />
        <span className="text-xs bg-gray-700 text-gray-400 rounded px-1.5 py-0.5">
          iter={step.iteration}
        </span>
        {step.checkpoint_id && (
          <button
            onClick={() => copyText(step.checkpoint_id!)}
            className="font-mono text-xs text-gray-500 hover:text-gray-300 transition-colors"
            title="Copy checkpoint ID"
          >
            chk={step.checkpoint_id.slice(0, 8)}
          </button>
        )}
        {step.attempt_count > 1 && (
          <span className="text-xs text-gray-500">×{step.attempt_count} attempts</span>
        )}
      </div>
    </div>
  )
}
