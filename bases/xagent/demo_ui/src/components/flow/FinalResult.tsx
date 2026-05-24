import type { AgentFlowState } from '../../types/agent_flow'

interface FinalResultProps {
  state: AgentFlowState
}

export function FinalResult({ state }: FinalResultProps) {
  const isCompleted = state.status === 'completed'
  const isFailed = state.status === 'failed'
  const hasErrors = state.errors.length > 0

  if (!isCompleted && !isFailed && !hasErrors) return null

  if (isCompleted) {
    return (
      <div className="rounded-xl border-2 border-green-600 bg-green-950/30 p-4 w-full max-w-4xl">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-green-400 font-bold">✓</span>
          <span className="text-sm font-semibold text-green-300">Completed</span>
        </div>
        {state.final_response && (
          <p className="text-sm text-green-200 line-clamp-3">
            {state.final_response}
          </p>
        )}
      </div>
    )
  }

  const lastError = state.errors[state.errors.length - 1]

  return (
    <div className="rounded-xl border-2 border-red-600 bg-red-950/30 p-4 w-full max-w-4xl">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-red-400 font-bold">✗</span>
        <span className="text-sm font-semibold text-red-300">Failed</span>
      </div>
      {lastError && (
        <p className="text-sm text-red-200">{lastError.message}</p>
      )}
    </div>
  )
}
