import type {
  AgentFlowIteration,
  RunAuditRecord,
  StepAuditEntry,
} from '../../types/agent_flow'
import { Arrow } from './Arrow'
import { StepNode } from './StepNode'
import { ParallelGroup } from './ParallelGroup'

interface IterationBlockProps {
  iteration: AgentFlowIteration
  audit: RunAuditRecord | null
  onSelectStep: (step: StepAuditEntry) => void
}

export function getAuditStep(
  audit: RunAuditRecord | null,
  iteration: number,
  stepName: string
): StepAuditEntry | null {
  if (!audit) return null
  return (
    audit.steps.find(
      (s) => s.iteration === iteration && s.step_name === stepName
    ) ?? null
  )
}

export function IterationBlock({
  iteration,
  audit,
  onSelectStep,
}: IterationBlockProps) {
  const plannerAudit = getAuditStep(audit, iteration.iteration, 'planner')
  const summaryAudit = getAuditStep(audit, iteration.iteration, 'summary')

  // Build subagent list from plan selections and/or subagent_results keys
  const subagentNames: string[] = []
  if (iteration.plan?.selections) {
    for (const sel of iteration.plan.selections) {
      if (!subagentNames.includes(sel.name)) subagentNames.push(sel.name)
    }
  }
  for (const name of Object.keys(iteration.subagent_results)) {
    if (!subagentNames.includes(name)) subagentNames.push(name)
  }
  // Also check audit for subagent steps in this iteration
  if (audit) {
    for (const step of audit.steps) {
      if (
        step.iteration === iteration.iteration &&
        step.step_name.startsWith('subagent:')
      ) {
        const name = step.step_name.slice('subagent:'.length)
        if (!subagentNames.includes(name)) subagentNames.push(name)
      }
    }
  }

  const subagentEntries = subagentNames.map((name) => ({
    name,
    auditStep: getAuditStep(audit, iteration.iteration, `subagent:${name}`),
  }))

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-4 w-full max-w-4xl">
      <div className="text-xs text-gray-500 mb-3 font-mono">
        ITERATION {iteration.iteration}
      </div>
      <div className="flex items-center gap-3 flex-wrap">
        <StepNode
          stepName="planner"
          stepType="planner"
          auditStep={plannerAudit}
          onSelectStep={onSelectStep}
        />
        <Arrow />
        <ParallelGroup
          subagents={subagentEntries}
          onSelectStep={onSelectStep}
        />
        <Arrow />
        <StepNode
          stepName="summary"
          stepType="summary"
          auditStep={summaryAudit}
          decisionLabel={iteration.summary?.decision}
          onSelectStep={onSelectStep}
        />
      </div>
    </div>
  )
}
