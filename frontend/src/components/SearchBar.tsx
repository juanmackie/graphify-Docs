interface Props {
  query: string
  onQuery: (q: string) => void
  resultCount: number
}

export default function SearchBar({ query, onQuery, resultCount }: Props) {
  return (
    <div className="search">
      <input
        type="text"
        value={query}
        placeholder="SEARCH NODES…"
        onChange={(e) => onQuery(e.target.value)}
        spellCheck={false}
      />
      {query && (
        <>
          <span className="search-count">
            {resultCount} match{resultCount === 1 ? '' : 'es'}
          </span>
          <button className="secondary tiny" onClick={() => onQuery('')} title="Clear search">
            ✕
          </button>
        </>
      )}
    </div>
  )
}
