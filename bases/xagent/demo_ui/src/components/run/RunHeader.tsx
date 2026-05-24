import { useState } from 'react'
import type { AgentFlowState } from '../../types/agent_flow'
import { StatusBadge } from '../shared/StatusBadge'
import { api } from '../../api/client'
import { SubmitInputForm } from './SubmitInputForm'

interface RunHeaderProps {
  state: AgentFlowState
  onUpdated: (run: AgentFlowState) => void
}

const TERMINAL = new Set(['completed', 'failed'])

export function RunHeader({ state, onUpdated }: RunHeaderProps) {
  const [resuming, setResuming] = useState(false)
  const [showInput, setShowInput] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isTerminal = TERMINAL.has(state.status)
  const isWaiting = state.status === 'waiting' || state.status === 'waiting_for_user'
  const showResume = !isTerminal && !isWaiting
  const showSubmit = isWaiting

  async function handleResume() {
    setResuming(true)
    setError(null)
    try {
      const updated = await api.resumeRun(state.run_id)
      onUpdated(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Resume failed')
    } finally {
      setResuming(false)
    }
  }

  function handleInputSubmitted(run: AgentFlowState) {
    setShowInput(false)
    onUpdated(run)
  }

  const metaEntries = Object.entries(state.metadata)

  return (
    <div className="sticky top-0 z-10 bg-gray-950 border-b border-gray-800 px-5 py-3">
      <div className="flex items-start gap-3 flex-wrap">
        <span className="font-mono text-sm text-gray-300 truncate max-w-[200px]">
          {state.run_id}
        </span>
        <span className="text-gray-600">•</span>
        <StatusBadge status={state.status} />
        <span className="text-gray-600">•</span>
        <span className="text-sm text-gray-200 line-clamp-2 max-w-sm">
          {state.user_query}
        </span>

        <div className="ml-auto flex items-center gap-2">
          {showResume && (
            <button
              onClick={handleResume}
              disabled={resuming}
              className="px-3 py-1 text-xs bg-blue-700 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed rounded text-white transition-colors"
            >
              {resuming ? 'Resuming…' : 'Resume'}
            </button>
          )}
          {showSubmit && (
            <button
              onClick={() => setShowInput((v) => !v)}
              className="px-3 py-1 text-xs bg-purple-700 hover:bg-purple-600 rounded text-white transition-colors"
            >
              Send Message
            </button>
          )}
        </div>
      </div>

      {metaEntries.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {metaEntries.map(([k, v]) => (
            <span
              key={k}
              className="text-xs bg-gray-800 text-gray-400 rounded px-2 py-0.5"
            >
              {k}: {String(v)}
            </span>
          ))}
        </div>
      )}

      <div className="mt-2 font-mono text-xs text-gray-600 truncate">
        conversation: {state.conversation_id}
      </div>

      {error && (
        <p className="text-xs text-red-400 mt-2">{error}</p>
      )}

      {showInput && (
        <div className="mt-3">
          <SubmitInputForm
            conversationId={state.conversation_id}
            onInputSubmitted={handleInputSubmitted}
            onCancel={() => setShowInput(false)}
          />
        </div>
      )}
    </div>
  )
}
