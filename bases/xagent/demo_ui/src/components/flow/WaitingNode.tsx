import type { UserRequest, WaitStepSpec } from '../../types/agent_flow'

interface WaitingNodeProps {
  request: UserRequest | null
  wait?: WaitStepSpec | null
}

export function WaitingNode({ request, wait }: WaitingNodeProps) {
  const prompt = request?.prompt ?? wait?.prompt
  return (
    <div className="rounded-xl border-2 border-purple-500 bg-purple-950/30 p-4 w-full max-w-4xl">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">⏸</span>
        <span className="text-sm font-semibold text-purple-300">
          Waiting for Message
        </span>
      </div>
      {prompt && (
        <p className="text-sm text-purple-200">{prompt}</p>
      )}
    </div>
  )
}
