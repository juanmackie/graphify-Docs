import { useMemo, useState } from 'react'
import type { GraphNode } from '../types'

export interface PathResult {
  start: string
  end: string
  nodes: Set<string>
  links: Set<string>
}

interface Props {
  nodes: GraphNode[]
  onResult: (startId: string, endId: string) => void
  onClear: () => void
  result: PathResult | null
  hops: number | null
}

export default function PathQuery({ nodes, onResult, onClear, result, hops }: Props) {
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')

  const sorted = useMemo(() => [...nodes].sort((a, b) => a.name.localeCompare(b.name)), [nodes])

  return (
    <div className="panel-section path-query">
      <h4>Path Trace</h4>
      <div className="path-controls">
        <select value={start} onChange={(e) => setStart(e.target.value)}>
          <option value="">FROM…</option>
          {sorted.map((n) => (
            <option key={n.id} value={n.id}>
              {n.name}
            </option>
          ))}
        </select>
        <select value={end} onChange={(e) => setEnd(e.target.value)}>
          <option value="">TO…</option>
          {sorted.map((n) => (
            <option key={n.id} value={n.id}>
              {n.name}
            </option>
          ))}
        </select>
        <div className="path-buttons">
          <button
            disabled={!start || !end}
            onClick={() => {
              onResult(start, end)
            }}
          >
            TRACE
          </button>
          <button
            className="secondary"
            onClick={() => {
              setStart('')
              setEnd('')
              onClear()
            }}
          >
            CLEAR
          </button>
        </div>
      </div>
      {result && (
        <p className="path-result">
          {hops !== null && hops > 0 ? `${hops} HOP${hops === 1 ? '' : 'S'}` : 'DIRECT LINK'} ·
          HIGHLIGHTED IN RED
        </p>
      )}
      {result && hops === null && <p className="path-result">NO PATH FOUND.</p>}
    </div>
  )
}
