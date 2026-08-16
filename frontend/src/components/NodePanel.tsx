import { useMemo } from 'react'
import type { GraphData, GraphNode } from '../types'
import { neighbors } from '../graphUtils'

interface Props {
  node: GraphNode
  graph: GraphData
  onClose: () => void
}

export default function NodePanel({ node, graph, onClose }: Props) {
  const rows = useMemo(() => neighbors(node.id, graph.nodes, graph.links), [node.id, graph])

  return (
    <aside className="node-panel">
      <div className="node-panel-header">
        <div>
          <span className="panel-kicker">Concept focus</span>
          <h3>{node.name}</h3>
        </div>
        <button className="secondary tiny" onClick={onClose}>
          ✕
        </button>
      </div>

      <dl className="node-facts">
        <div>
          <dt>Type</dt>
          <dd>{node.type}</dd>
        </div>
        <div>
          <dt>Degree</dt>
          <dd>{node.degree}</dd>
        </div>
        <div>
          <dt>Mentions</dt>
          <dd>{node.count}</dd>
        </div>
        <div>
          <dt>Community</dt>
          <dd>{node.community}</dd>
        </div>
        <div>
          <dt>Sources</dt>
          <dd>{node.sources.join(', ')}</dd>
        </div>
      </dl>

      <p className="node-explanation">
        Solid arrows are extracted statements. Faint double-ended links indicate nearby concepts, not a claimed direction.
      </p>

      {node.snippet && (
        <div className="node-snippet">
          <strong>In context:</strong>
          <p>{node.snippet}</p>
        </div>
      )}

      <div className="node-neighbors">
        <strong>Neighbors ({rows.length})</strong>
        <ul>
          {rows.slice(0, 18).map((row) => {
            const arrow = row.direction === 'both' ? '↔' : row.direction === 'out' ? '→' : '←'
            const evidence = row.evidence.length > 0 ? row.evidence : row.snippet ? [{ text: row.snippet }] : []
            return (
              <li key={`${row.direction}-${row.id}-${row.relation}`} className="neighbor-row">
                <div className="neighbor-line">
                  <span className={`dir ${row.direction}`}>{arrow}</span>
                  <span className="rel">{row.relation}</span>
                  <span className="nb-name">{row.name}</span>
                </div>
                <div className="neighbor-meta">
                  {row.kind} · {row.tag} · W{row.weight} · {Math.round(row.confidence * 100)}% confidence
                </div>
                {row.originalRelation && row.originalRelation !== row.relation && (
                  <div className="neighbor-original">model label: {row.originalRelation}</div>
                )}
                {evidence.length > 0 && (
                  <details className="neighbor-evidence">
                    <summary>evidence ({evidence.length})</summary>
                    {evidence.map((item, index) => (
                      <p key={`${item.text}-${index}`}>
                        {item.text}
                        {(item.chunk_index !== undefined || item.paragraph_index !== undefined) && (
                          <small>
                            {' '}
                            [{item.chunk_index !== undefined ? `chunk ${item.chunk_index}` : ''}
                            {item.paragraph_index !== undefined ? ` paragraph ${item.paragraph_index}` : ''}]
                          </small>
                        )}
                      </p>
                    ))}
                  </details>
                )}
              </li>
            )
          })}
          {rows.length > 18 && <li className="muted">Showing the 18 strongest connections.</li>}
          {rows.length === 0 && <li className="muted">No connections</li>}
        </ul>
      </div>
    </aside>
  )
}
