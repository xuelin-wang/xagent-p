import type { AgentFlowState, RunStatus } from '../../types/agent_flow'

interface RunListItemProps {
  run: AgentFlowState
  selected: boolean
  onClick: () => void
}

const dotColor: Record<RunStatus, string> = {
  pending: 'bg-gray-400',
  running: 'bg-amber-400 animate-pulse',
  paused: 'bg-blue-400',
  waiting_for_user: 'bg-purple-400',
  failed: 'bg-red-500',
  completed: 'bg-green-500',
}

export function RunListItem({ run, selected, onClick }: RunListItemProps) {
  const dot = dotColor[run.status] ?? 'bg-gray-400'
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2 transition-colors flex items-start gap-2 ${
        selected
          ? 'bg-gray-800 border-l-2 border-blue-500'
          : 'border-l-2 border-transparent hover:bg-gray-800/60'
      }`}
    >
      <span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${dot}`} />
      <div className="min-w-0">
        <div className="font-mono text-xs text-gray-300 truncate">
          {run.run_id.slice(0, 12)}
        </div>
        <div className="text-xs text-gray-500 truncate leading-tight">
          {run.user_query}
        </div>
      </div>
    </button>
  )
}
