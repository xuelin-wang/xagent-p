import type { AgentFlowState, RunAuditRecord } from '../types/agent_flow'

const BASE = '/agent-flow'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  listRuns(): Promise<AgentFlowState[]> {
    return request<AgentFlowState[]>(`${BASE}/runs`)
  },

  createRun(payload: {
    query: string
    case_id?: string
    metadata?: Record<string, unknown>
  }): Promise<AgentFlowState> {
    return request<AgentFlowState>(`${BASE}/runs`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getRun(id: string): Promise<AgentFlowState> {
    return request<AgentFlowState>(`${BASE}/runs/${encodeURIComponent(id)}`)
  },

  resumeRun(id: string): Promise<AgentFlowState> {
    return request<AgentFlowState>(
      `${BASE}/runs/${encodeURIComponent(id)}/resume`,
      { method: 'POST' }
    )
  },

  submitInput(id: string, content: string): Promise<AgentFlowState> {
    return request<AgentFlowState>(
      `${BASE}/runs/${encodeURIComponent(id)}/input`,
      {
        method: 'POST',
        body: JSON.stringify({ content }),
      }
    )
  },

  getAudit(id: string): Promise<RunAuditRecord> {
    return request<RunAuditRecord>(
      `${BASE}/runs/${encodeURIComponent(id)}/audit`
    )
  },
}
