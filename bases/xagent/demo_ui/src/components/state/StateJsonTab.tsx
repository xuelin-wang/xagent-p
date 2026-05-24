import { useState } from 'react'
import type { AgentFlowState } from '../../types/agent_flow'
import { JsonViewer } from '../shared/JsonViewer'

interface StateJsonTabProps {
  state: AgentFlowState
}

export function StateJsonTab({ state }: StateJsonTabProps) {
  const [raw, setRaw] = useState(false)

  function handleCopy() {
    void navigator.clipboard.writeText(JSON.stringify(state, null, 2))
  }

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-gray-500 font-mono">AgentFlowState</span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setRaw((v) => !v)}
            className={`text-xs rounded px-2 py-0.5 transition-colors ${
              raw
                ? 'bg-gray-600 text-gray-200'
                : 'bg-gray-800 text-gray-400 hover:text-gray-200'
            }`}
          >
            Raw
          </button>
          <button
            onClick={handleCopy}
            className="text-xs bg-gray-800 text-gray-400 hover:text-gray-200 rounded px-2 py-0.5 transition-colors"
          >
            Copy
          </button>
        </div>
      </div>

      {raw ? (
        <pre className="bg-gray-900 rounded p-3 text-xs font-mono text-gray-200 overflow-auto max-h-[70vh]">
          {JSON.stringify(state, null, 2)}
        </pre>
      ) : (
        <div className="bg-gray-900 rounded p-3 text-xs font-mono overflow-auto max-h-[70vh]">
          <JsonViewer data={state} depth={0} />
        </div>
      )}
    </div>
  )
}
