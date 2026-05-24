import { useState } from 'react'

interface JsonViewerProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any
  depth?: number
}

const COLLAPSE_THRESHOLD = 3
const STRING_TRUNCATE = 200

export function JsonViewer({ data, depth = 0 }: JsonViewerProps) {
  const startCollapsed = depth >= 2
  const [collapsed, setCollapsed] = useState(startCollapsed)
  const indent = depth * 12

  if (data === null || data === undefined) {
    return <span className="text-gray-400">null</span>
  }

  if (typeof data === 'boolean') {
    return <span className="text-blue-400">{data ? 'true' : 'false'}</span>
  }

  if (typeof data === 'number') {
    return <span className="text-blue-400">{data}</span>
  }

  if (typeof data === 'string') {
    const display =
      data.length > STRING_TRUNCATE ? data.slice(0, STRING_TRUNCATE) + '…' : data
    return <span className="text-green-400">"{display}"</span>
  }

  if (Array.isArray(data)) {
    if (data.length === 0) {
      return <span className="text-gray-300">[]</span>
    }
    if (data.length > COLLAPSE_THRESHOLD) {
      if (collapsed) {
        return (
          <button
            onClick={() => setCollapsed(false)}
            className="text-gray-400 hover:text-gray-200 cursor-pointer"
          >
            [...{data.length} items]
          </button>
        )
      }
      return (
        <span>
          <button
            onClick={() => setCollapsed(true)}
            className="text-gray-400 hover:text-gray-200 cursor-pointer"
          >
            [
          </button>
          <div style={{ marginLeft: indent + 12 }}>
            {data.map((item, i) => (
              <div key={i} className="my-0.5">
                <JsonViewer data={item} depth={depth + 1} />
                {i < data.length - 1 && (
                  <span className="text-gray-500">,</span>
                )}
              </div>
            ))}
          </div>
          <span className="text-gray-400">]</span>
        </span>
      )
    }
    return (
      <span>
        <span className="text-gray-400">[</span>
        <div style={{ marginLeft: indent + 12 }}>
          {data.map((item, i) => (
            <div key={i} className="my-0.5">
              <JsonViewer data={item} depth={depth + 1} />
              {i < data.length - 1 && <span className="text-gray-500">,</span>}
            </div>
          ))}
        </div>
        <span className="text-gray-400">]</span>
      </span>
    )
  }

  if (typeof data === 'object') {
    const keys = Object.keys(data as Record<string, unknown>)
    if (keys.length === 0) {
      return <span className="text-gray-300">{'{}'}</span>
    }
    if (keys.length > COLLAPSE_THRESHOLD) {
      if (collapsed) {
        return (
          <button
            onClick={() => setCollapsed(false)}
            className="text-gray-400 hover:text-gray-200 cursor-pointer"
          >
            {'{'}&hellip;{keys.length} keys{'}'}
          </button>
        )
      }
      return (
        <span>
          <button
            onClick={() => setCollapsed(true)}
            className="text-gray-400 hover:text-gray-200 cursor-pointer"
          >
            {'{'}
          </button>
          <div style={{ marginLeft: indent + 12 }}>
            {keys.map((k, i) => (
              <div key={k} className="my-0.5">
                <span className="text-purple-300">"{k}"</span>
                <span className="text-gray-500">: </span>
                <JsonViewer
                  data={(data as Record<string, unknown>)[k]}
                  depth={depth + 1}
                />
                {i < keys.length - 1 && (
                  <span className="text-gray-500">,</span>
                )}
              </div>
            ))}
          </div>
          <span className="text-gray-400">{'}'}</span>
        </span>
      )
    }
    return (
      <span>
        <span className="text-gray-400">{'{'}</span>
        <div style={{ marginLeft: indent + 12 }}>
          {keys.map((k, i) => (
            <div key={k} className="my-0.5">
              <span className="text-purple-300">"{k}"</span>
              <span className="text-gray-500">: </span>
              <JsonViewer
                data={(data as Record<string, unknown>)[k]}
                depth={depth + 1}
              />
              {i < keys.length - 1 && <span className="text-gray-500">,</span>}
            </div>
          ))}
        </div>
        <span className="text-gray-400">{'}'}</span>
      </span>
    )
  }

  return <span className="text-gray-300">{String(data)}</span>
}
