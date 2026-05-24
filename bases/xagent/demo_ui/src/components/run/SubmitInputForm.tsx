import { useState } from 'react'
import { api } from '../../api/client'
import type { AgentFlowState } from '../../types/agent_flow'

interface SubmitInputFormProps {
  conversationId: string
  onInputSubmitted: (run: AgentFlowState) => void
  onCancel: () => void
}

export function SubmitInputForm({
  conversationId,
  onInputSubmitted,
  onCancel,
}: SubmitInputFormProps) {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!content.trim()) return
    setLoading(true)
    setError(null)
    try {
      const run = await api.sendMessage({
        conversation_id: conversationId,
        content,
      })
      onInputSubmitted(run)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Send failed')
      setLoading(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-gray-900 border border-gray-700 rounded-lg p-3 flex flex-col gap-2"
    >
      <textarea
        autoFocus
        rows={2}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="New message…"
        className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500 resize-none"
      />
      {error && <p className="text-xs text-red-400">{error}</p>}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1 text-xs text-gray-400 hover:text-gray-200 transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={loading || !content.trim()}
          className="px-3 py-1 text-xs bg-purple-700 hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed rounded text-white transition-colors"
        >
          {loading ? 'Sending…' : 'Send Message'}
        </button>
      </div>
    </form>
  )
}
