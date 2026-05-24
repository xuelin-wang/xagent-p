type Tab = 'flow' | 'audit' | 'state'

interface TabBarProps {
  active: Tab
  onChange: (t: Tab) => void
  auditDot: boolean
}

const tabs: { id: Tab; label: string }[] = [
  { id: 'flow', label: 'Flow Chart' },
  { id: 'audit', label: 'Audit Log' },
  { id: 'state', label: 'State JSON' },
]

export function TabBar({ active, onChange, auditDot }: TabBarProps) {
  return (
    <div className="flex border-b border-gray-800 bg-gray-950">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`px-4 py-2 text-sm flex items-center gap-1.5 transition-colors ${
            active === tab.id
              ? 'border-b-2 border-blue-500 text-gray-100'
              : 'text-gray-500 hover:text-gray-300 border-b-2 border-transparent'
          }`}
        >
          {tab.label}
          {tab.id === 'audit' && auditDot && (
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
          )}
        </button>
      ))}
    </div>
  )
}
