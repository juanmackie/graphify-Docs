import { communityColor, TAG_COLORS, TAG_LABELS } from '../colors'

interface Props {
  communityCount: number
}

export default function Legend({ communityCount }: Props) {
  const shown = Math.min(communityCount, 12)
  return (
    <div className="panel-section legend">
      <h4>Communities</h4>
      {shown === 0 ? (
        <p className="muted">No communities yet</p>
      ) : (
        <div className="swatch-list">
          {Array.from({ length: shown }, (_, i) => (
            <div className="swatch-row" key={i}>
              <span className="swatch" style={{ background: communityColor(i) }} />
              <span>{i === 0 ? `Community 0 (largest)` : `Community ${i}`}</span>
            </div>
          ))}
        </div>
      )}
      <h4>Edge sources</h4>
      <div className="swatch-list">
        {(['llm', 'cooccurrence', 'both'] as const).map((tag) => (
          <div className="swatch-row" key={tag}>
            <span className="swatch" style={{ background: TAG_COLORS[tag] }} />
            <span>{TAG_LABELS[tag]}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
