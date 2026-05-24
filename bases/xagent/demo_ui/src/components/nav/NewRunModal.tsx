import { useState } from 'react'
import { api } from '../../api/client'
import type { AgentFlowState } from '../../types/agent_flow'

interface NewRunModalProps {
  onClose: () => void
  onRunStarted: (run: AgentFlowState) => void
}

export function NewRunModal({ onClose, onRunStarted }: NewRunModalProps) {
  const [query, setQuery] = useState('')
  const [caseId, setCaseId] = useState('')
  const [metaRaw, setMetaRaw] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    let metadata: Record<string, unknown> | undefined
    if (metaRaw.trim()) {
      try {
        metadata = JSON.parse(metaRaw) as Record<string, unknown>
      } catch {
        setError('Metadata is not valid JSON')
        return
      }
    }

    setLoading(true)
    try {
      const run = await api.createRun({
        query,
        case_id: caseId.trim() || undefined,
        metadata,
      })
      onRunStarted(run)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start run')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-md shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-700">
          <h2 className="text-sm font-semibold text-gray-100">New Run</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-200 text-lg leading-none"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-5 py-4 flex flex-col gap-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Query <span className="text-red-400">*</span>
            </label>
            <textarea
              required
              rows={3}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500 resize-none"
              placeholder="What should the agent do?"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Case ID <span className="text-gray-600">(optional)</span>
            </label>
            <input
              type="text"
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
              className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
              placeholder="e.g. case-123"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Metadata JSON <span className="text-gray-600">(optional)</span>
            </label>
            <textarea
              rows={3}
              value={metaRaw}
              onChange={(e) => setMetaRaw(e.target.value)}
              className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm font-mono text-gray-100 focus:outline-none focus:border-blue-500 resize-none"
              placeholder='{"key": "value"}'
            />
          </div>

          {error && (
            <p className="text-xs text-red-400 bg-red-950/40 rounded px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-1.5 text-sm text-gray-300 hover:text-gray-100 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="px-4 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded text-white transition-colors"
            >
              {loading ? 'Starting…' : 'Start'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
