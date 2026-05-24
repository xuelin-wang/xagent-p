export type RunStatus =
  | 'pending'
  | 'running'
  | 'paused'
  | 'waiting_for_user'
  | 'failed'
  | 'completed'

export type FlowStage =
  | 'start'
  | 'planning'
  | 'subagents'
  | 'summarizing'
  | 'waiting_for_user'
  | 'finalizing'
  | 'completed'
  | 'failed'

export type StepStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'skipped'

export type SummaryDecision = 'final' | 'replan' | 'ask_user' | 'fail'

export interface PlanSubagentSelection {
  name: string
  reason: string
}

export interface PlanOutput {
  goal: string
  selections: PlanSubagentSelection[]
  rationale: string
}

export interface SubagentResult {
  name: string
  status: 'completed' | 'timeout' | 'error' | 'skipped'
  content: string
}

export interface UserRequest {
  request_id: string
  prompt: string
}

export interface SummaryOutput {
  decision: SummaryDecision
  answer_draft: string | null
  rationale: string | null
  missing_information: string[]
  user_request: UserRequest | null
}

export interface AgentFlowIteration {
  iteration: number
  plan: PlanOutput | null
  subagent_results: Record<string, SubagentResult>
  summary: SummaryOutput | null
  tool_results: Record<string, ToolResult>
}

export interface ToolResult {
  [key: string]: unknown
}

export interface AgentError {
  stage: string
  step_name: string | null
  message: string
  retryable: boolean
}

export interface UserInputEvent {
  run_id: string
  content: string
  request_id: string
}

export interface AgentFlowState {
  run_id: string
  user_query: string
  case_id: string | null
  status: RunStatus
  current_stage: FlowStage
  current_iteration: number
  iterations: AgentFlowIteration[]
  final_response: string | null
  pending_user_request: UserRequest | null
  metadata: Record<string, unknown>
  errors: AgentError[]
  user_input_events: UserInputEvent[]
}

export interface StepAuditEntry {
  step_id: string
  step_name: string
  step_type: 'planner' | 'subagent' | 'summary' | 'tool_call'
  iteration: number
  status: StepStatus
  attempt_count: number
  input_json: Record<string, unknown>
  output_json: Record<string, unknown> | null
  error_json: Record<string, unknown> | null
  checkpoint_id?: string
}

export interface RunAuditRecord {
  run_id: string
  status: RunStatus
  user_query: string
  final_response: string | null
  current_iteration: number
  steps: StepAuditEntry[]
  user_input_events: UserInputEvent[]
}
