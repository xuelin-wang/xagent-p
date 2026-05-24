import { useState } from 'react'
import type { AgentFlowState } from '../../types/agent_flow'
import { RunListItem } from './RunListItem'
import { NewRunModal } from './NewRunModal'

interface NavPanelProps {
  runs: AgentFlowState[]
  selectedRunId: string | null
  onSelect: (id: string) => void
  onRunStarted: (run: AgentFlowState) => void
}

export function NavPanel({
  runs,
  selectedRunId,
  onSelect,
  onRunStarted,
}: NavPanelProps) {
  const [showModal, setShowModal] = useState(false)

  function handleRunStarted(run: AgentFlowState) {
    setShowModal(false)
    onRunStarted(run)
  }

  return (
    <>
      <nav className="w-[220px] shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col overflow-hidden h-full">
        <div className="flex items-center justify-between px-3 py-3 border-b border-gray-800">
          <span className="text-sm font-semibold text-gray-100">
            ⬡ Agent Flow
          </span>
          <button
            onClick={() => setShowModal(true)}
            className="text-xs bg-blue-700 hover:bg-blue-600 text-white rounded px-2 py-1 transition-colors"
          >
            + New Run
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {runs.length === 0 ? (
            <p className="text-xs text-gray-500 text-center mt-8 px-4">
              No runs yet — start one above
            </p>
          ) : (
            runs.map((run) => (
              <RunListItem
                key={run.run_id}
                run={run}
                selected={run.run_id === selectedRunId}
                onClick={() => onSelect(run.run_id)}
              />
            ))
          )}
        </div>
      </nav>

      {showModal && (
        <NewRunModal
          onClose={() => setShowModal(false)}
          onRunStarted={handleRunStarted}
        />
      )}
    </>
  )
}
