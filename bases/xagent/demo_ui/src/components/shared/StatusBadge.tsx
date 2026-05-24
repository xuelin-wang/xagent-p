interface StatusBadgeProps {
  status: string
}

const colorMap: Record<string, string> = {
  pending: 'bg-gray-600 text-gray-100',
  running: 'bg-amber-600 text-white animate-pulse',
  succeeded: 'bg-green-700 text-white',
  completed: 'bg-green-700 text-white',
  failed: 'bg-red-700 text-white',
  waiting_for_user: 'bg-purple-700 text-white',
  skipped: 'bg-slate-600 text-slate-200',
  paused: 'bg-blue-700 text-white',
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const cls = colorMap[status] ?? 'bg-gray-600 text-gray-100'
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${cls}`}
    >
      {status}
    </span>
  )
}
