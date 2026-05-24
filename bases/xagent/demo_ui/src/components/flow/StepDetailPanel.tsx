import { useState } from 'react'
import type { StepAuditEntry } from '../../types/agent_flow'
import { StatusBadge } from '../shared/StatusBadge'
import { JsonViewer } from '../shared/JsonViewer'

interface StepDetailPanelProps {
  step: StepAuditEntry | null
  onClose: () => void
}

interface CollapsibleSectionProps {
  title: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any
  defaultOpen?: boolean
}

function CollapsibleSection({
  title,
  data,
  defaultOpen = true,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-t border-gray-700 pt-3 mt-3">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-200 w-full mb-2"
      >
        <span>{open ? '▾' : '▸'}</span>
        <span className="font-semibold uppercase tracking-wide">{title}</span>
      </button>
      {open && (
        <div className="bg-gray-950 rounded p-2 text-xs font-mono overflow-auto max-h-64">
          <JsonViewer data={data} depth={0} />
        </div>
      )}
    </div>
  )
}

export function StepDetailPanel({ step, onClose }: StepDetailPanelProps) {
  const open = step !== null

  function copyCheckpoint() {
    if (step?.checkpoint_id) {
      void navigator.clipboard.writeText(step.checkpoint_id)
    }
  }

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 bg-black/20 z-40"
          onClick={onClose}
        />
      )}
      <div
        className={`fixed top-0 right-0 h-full w-96 bg-gray-900 border-l border-gray-700 shadow-2xl z-50 overflow-y-auto transition-transform duration-300 ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {step && (
          <div className="p-4">
            <div className="flex items-center justify-between mb-4">
              <span className="font-mono text-sm text-gray-100 truncate">
                {step.step_name}
              </span>
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-200 text-lg leading-none ml-2 shrink-0"
              >
                ✕
              </button>
            </div>

            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs bg-gray-700 text-gray-300 rounded px-2 py-0.5">
                {step.step_type}
              </span>
              <StatusBadge status={step.status} />
            </div>

            <div className="text-xs text-gray-400 mb-2">
              Iteration {step.iteration} • attempt {step.attempt_count}
            </div>

            {step.checkpoint_id && (
              <div className="flex items-center gap-2 text-xs text-gray-400 font-mono mb-2">
                <span>Checkpoint: {step.checkpoint_id.slice(0, 16)}…</span>
                <button
                  onClick={copyCheckpoint}
                  className="text-blue-400 hover:text-blue-300"
                  title="Copy checkpoint ID"
                >
                  ⎘
                </button>
              </div>
            )}

            {step.status === 'skipped' && (
              <div className="bg-blue-950/40 border border-blue-700 rounded px-3 py-2 text-xs text-blue-300 mb-3">
                ↺ Replayed from checkpoint
              </div>
            )}

            <CollapsibleSection title="Input" data={step.input_json} />
            {step.output_json !== null && (
              <CollapsibleSection title="Output" data={step.output_json} />
            )}
            {step.error_json !== null && (
              <CollapsibleSection title="Error" data={step.error_json} defaultOpen={true} />
            )}
          </div>
        )}
      </div>
    </>
  )
}
