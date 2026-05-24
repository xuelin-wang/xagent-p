import { useState, useEffect, useRef, useCallback } from 'react'
import type { AgentFlowState, RunAuditRecord, StepAuditEntry } from './types/agent_flow'
import { api } from './api/client'
import { NavPanel } from './components/nav/NavPanel'
import { RunHeader } from './components/run/RunHeader'
import { TabBar } from './components/run/TabBar'
import { FlowChart } from './components/flow/FlowChart'
import { StepDetailPanel } from './components/flow/StepDetailPanel'
import { AuditLog } from './components/audit/AuditLog'
import { StateJsonTab } from './components/state/StateJsonTab'

type Tab = 'flow' | 'audit' | 'state'

const TERMINAL = new Set(['completed', 'failed'])
const RUNS_POLL_MS = 3000
const RUN_POLL_MS = 2000

export default function App() {
  const [runs, setRuns] = useState<AgentFlowState[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [selectedRun, setSelectedRun] = useState<AgentFlowState | null>(null)
  const [audit, setAudit] = useState<RunAuditRecord | null>(null)
  const [activeTab, setActiveTab] = useState<Tab>('flow')
  const [selectedStep, setSelectedStep] = useState<StepAuditEntry | null>(null)
  const [auditDot, setAuditDot] = useState(false)

  const activeTabRef = useRef<Tab>(activeTab)
  useEffect(() => {
    activeTabRef.current = activeTab
    if (activeTab === 'audit') setAuditDot(false)
  }, [activeTab])

  const prevAuditCountRef = useRef(0)

  // Poll list of runs every 3s
  useEffect(() => {
    let alive = true

    async function poll() {
      if (!alive) return
      try {
        const data = await api.listRuns()
        if (alive) setRuns(data)
      } catch {
        // ignore transient errors
      }
      if (alive) setTimeout(poll, RUNS_POLL_MS)
    }

    void poll()
    return () => {
      alive = false
    }
  }, [])

  // Poll selected run + audit every 2s while non-terminal
  const startRunPoll = useCallback((runId: string) => {
    let alive = true
    prevAuditCountRef.current = 0

    async function poll() {
      if (!alive) return
      try {
        const [run, auditRecord] = await Promise.all([
          api.getRun(runId),
          api.getAudit(runId),
        ])
        if (!alive) return

        setSelectedRun(run)
        setAudit(auditRecord)

        // Update runs list entry
        setRuns((prev) =>
          prev.map((r) => (r.run_id === run.run_id ? run : r))
        )

        // Detect new audit steps for dot indicator
        const newCount = auditRecord.steps.length
        if (
          newCount > prevAuditCountRef.current &&
          activeTabRef.current !== 'audit'
        ) {
          setAuditDot(true)
        }
        prevAuditCountRef.current = newCount

        if (!TERMINAL.has(run.status)) {
          setTimeout(poll, RUN_POLL_MS)
        }
      } catch {
        if (alive) setTimeout(poll, RUN_POLL_MS)
      }
    }

    void poll()
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    if (!selectedRunId) {
      setSelectedRun(null)
      setAudit(null)
      setAuditDot(false)
      return
    }
    setSelectedRun(null)
    setAudit(null)
    setAuditDot(false)
    setActiveTab('flow')
    setSelectedStep(null)
    prevAuditCountRef.current = 0

    const cleanup = startRunPoll(selectedRunId)
    return cleanup
  }, [selectedRunId, startRunPoll])

  function handleRunStarted(run: AgentFlowState) {
    setRuns((prev) => {
      const exists = prev.find((r) => r.run_id === run.run_id)
      return exists ? prev.map((r) => (r.run_id === run.run_id ? run : r)) : [run, ...prev]
    })
    setSelectedRunId(run.run_id)
  }

  function handleRunUpdated(run: AgentFlowState) {
    setSelectedRun(run)
    setRuns((prev) =>
      prev.map((r) => (r.run_id === run.run_id ? run : r))
    )
  }

  return (
    <div className="bg-gray-950 text-gray-100 h-screen flex overflow-hidden">
      <NavPanel
        runs={runs}
        selectedRunId={selectedRunId}
        onSelect={setSelectedRunId}
        onRunStarted={handleRunStarted}
      />

      <main className="flex-1 flex flex-col overflow-hidden h-full">
        {selectedRun ? (
          <>
            <RunHeader state={selectedRun} onUpdated={handleRunUpdated} />
            <TabBar
              active={activeTab}
              onChange={setActiveTab}
              auditDot={auditDot}
            />
            <div className="flex-1 overflow-y-auto">
              {activeTab === 'flow' && (
                <FlowChart
                  state={selectedRun}
                  audit={audit}
                  onSelectStep={setSelectedStep}
                />
              )}
              {activeTab === 'audit' && (
                <AuditLog audit={audit} state={selectedRun} />
              )}
              {activeTab === 'state' && (
                <StateJsonTab state={selectedRun} />
              )}
            </div>
            <StepDetailPanel
              step={selectedStep}
              onClose={() => setSelectedStep(null)}
            />
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-gray-600 text-sm">
              Select a run from the left panel or start a new one.
            </p>
          </div>
        )}
      </main>
    </div>
  )
}
