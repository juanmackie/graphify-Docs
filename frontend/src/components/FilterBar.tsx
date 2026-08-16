import type { Filters } from '../graphUtils'
import { TAG_LABELS } from '../colors'

interface Props {
  relations: { relation: string; count: number }[]
  filters: Filters
  onChange: (f: Filters) => void
  maxWeight: number
}

const ALL_TAGS = ['llm', 'cooccurrence', 'both'] as const
const ALL_KINDS = ['assertion', 'association'] as const
const KIND_LABELS: Record<string, string> = {
  assertion: 'DIRECTED ASSERTION',
  association: 'UNDIRECTED ASSOCIATION',
}

export default function FilterBar({ relations, filters, onChange, maxWeight }: Props) {
  const toggleTag = (tag: string) => {
    const next = new Set(filters.tags)
    if (next.has(tag)) next.delete(tag)
    else next.add(tag)
    onChange({ ...filters, tags: next })
  }

  const toggleRelation = (relation: string) => {
    const next = new Set(filters.relations)
    if (next.has(relation)) next.delete(relation)
    else next.add(relation)
    onChange({ ...filters, relations: next })
  }

  const setAllRelations = () => onChange({ ...filters, relations: new Set(relations.map((r) => r.relation)) })

  const toggleKind = (kind: string) => {
    const next = new Set(filters.kinds)
    if (next.has(kind as typeof ALL_KINDS[number])) next.delete(kind as typeof ALL_KINDS[number])
    else next.add(kind as typeof ALL_KINDS[number])
    onChange({ ...filters, kinds: next })
  }

  const setAllKinds = () => onChange({ ...filters, kinds: new Set(ALL_KINDS) })

  return (
    <div className="panel-section filters">
      <h4>Edge filters</h4>

      <div className="filter-group">
        <div className="filter-label">Provenance</div>
        {ALL_TAGS.map((tag) => (
          <label className="checkbox-row" key={tag}>
            <input
              type="checkbox"
              checked={filters.tags.has(tag)}
              onChange={() => toggleTag(tag)}
            />
            <span>{TAG_LABELS[tag]}</span>
          </label>
        ))}
      </div>

      <div className="filter-group">
        <div className="filter-label">
          Semantics
          <button className="link-btn" onClick={setAllKinds}>
            all
          </button>
        </div>
        {ALL_KINDS.map((kind) => (
          <label className="checkbox-row" key={kind}>
            <input
              type="checkbox"
              checked={filters.kinds.has(kind)}
              onChange={() => toggleKind(kind)}
            />
            <span>{KIND_LABELS[kind]}</span>
          </label>
        ))}
      </div>

      <div className="filter-group">
        <div className="filter-label">
          Relation type
          <button className="link-btn" onClick={setAllRelations}>
            all
          </button>
        </div>
        <div className="relation-list">
          {relations.length === 0 && <span className="muted">No relations</span>}
          {relations.map((r) => (
            <label className="checkbox-row" key={r.relation}>
              <input
                type="checkbox"
                checked={filters.relations.has(r.relation)}
                onChange={() => toggleRelation(r.relation)}
              />
              <span className="rel-name">{r.relation}</span>
              <span className="rel-count">{r.count}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="filter-group">
        <div className="filter-label">
          Min inferred support <span className="muted">≥ {filters.minWeight}</span>
        </div>
        <input
          type="range"
          min={1}
          max={Math.max(1, maxWeight)}
          value={filters.minWeight}
          onChange={(e) => onChange({ ...filters, minWeight: Number(e.target.value) })}
        />
      </div>

      <div className="filter-group">
        <div className="filter-label">
          Min confidence <span className="muted">≥ {Math.round(filters.minConfidence * 100)}%</span>
        </div>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={filters.minConfidence}
          onChange={(e) => onChange({ ...filters, minConfidence: Number(e.target.value) })}
        />
      </div>
    </div>
  )
}
