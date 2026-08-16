import type { DocumentRecord } from '../types'
import { parseStageStats, stageTimingLine, stageTimings } from '../graphUtils'

interface Props {
  documents: DocumentRecord[]
  onOpen: (id: string) => void
  onDelete: (id: string) => void
  onReprocess: (id: string) => Promise<void>
}

const STATUS_LABEL: Record<DocumentRecord['status'], string> = {
  queued: 'QUEUED',
  parsing: 'PARSE',
  chunking: 'CHUNK',
  extracting: 'EXTRACT',
  clustering: 'CLUSTER',
  done: 'READY',
  error: 'FAIL',
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** Human "Ns ago" from an ISO timestamp (heartbeat = doc.updated_at). */
function timeAgo(iso: string): string {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000))
  if (s < 5) return 'just now'
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  return `${Math.floor(m / 60)}h ${m % 60}m ago`
}

function progressDetail(raw?: string | null): Record<string, number> | null {
  if (!raw) return null
  try {
    const value = JSON.parse(raw) as unknown
    return value && typeof value === 'object' ? value as Record<string, number> : null
  } catch {
    return null
  }
}

function formatEta(seconds?: number): string {
  if (!seconds || seconds < 1) return 'calculating ETA'
  if (seconds < 60) return `~${Math.ceil(seconds)}s left`
  return `~${Math.ceil(seconds / 60)}m left`
}

export default function DocumentList({ documents, onOpen, onDelete, onReprocess }: Props) {
  if (documents.length === 0) {
    return (
      <section className="card">
        <h2>Document Registry</h2>
        <p className="muted">NO DOCUMENTS ON FILE — UPLOAD ABOVE TO BEGIN.</p>
      </section>
    )
  }

  return (
    <section className="card">
      <h2>Document Registry</h2>
      <ul className="doc-list">
        {documents.map((doc) => {
          const done = doc.status === 'done'
          const failed = doc.status === 'error'
          const inflight = !done && !failed
          // Stage timing breakdown (parse · llm · total) for finished docs.
          const stageStats = done ? parseStageStats(doc.stats_json) : null
          const timings = stageStats ? stageTimings(stageStats) : []
          const extractionCtx: string[] = []
          if (stageStats?.chunks) extractionCtx.push(`${stageStats.chunks} chunks`)
          if (stageStats?.llmUsed) {
            if (stageStats.llmSelectedChunks) extractionCtx.push(`${stageStats.llmSelectedChunks} LLM-selected`)
            if (stageStats.llmConcurrency) extractionCtx.push(`concurrency ${stageStats.llmConcurrency}`)
          }
          // A job that hasn't written a heartbeat in a while is likely hung on
          // an upstream LLM call — surface it instead of an eternal spinner.
          const stale = inflight && Date.now() - new Date(doc.updated_at).getTime() > 120_000
          const detail = progressDetail(doc.progress_detail)
          return (
            <li key={doc.id} className="doc-row">
              <div className="doc-main">
                <span className="doc-name">{doc.name}</span>
                <span className="doc-meta muted">
                  {fmtSize(doc.size)} · {doc.node_count} nodes · {doc.edge_count} edges
                  {doc.extraction_mode ? ` · ${doc.extraction_mode.toUpperCase()}` : ''}
                </span>
                {timings.length > 0 && (
                  <span className="stage-times muted">
                    {stageTimingLine(stageStats)}
                    {extractionCtx.length > 0 ? ` · ${extractionCtx.join(' · ')}` : ''}
                  </span>
                )}
                {failed && doc.error && <span className="doc-error">{doc.error}</span>}
                {inflight && (
                  <span className={`doc-meta muted ${stale ? 'doc-error' : ''}`}>
                    {detail && detail.total > 0
                      ? `${detail.completed} / ${detail.total} selected chunks · ${formatEta(detail.eta_seconds)}`
                      : `last activity ${timeAgo(doc.updated_at)}`}
                    {stale ? ' — looks stalled, check backend logs' : ''}
                  </span>
                )}
              </div>
              <div className="doc-side">
                {inflight && (
                  <div className="progress-wrap">
                    <div className="progress" style={{ width: `${Math.round(doc.progress * 100)}%` }} />
                  </div>
                )}
                <span className={`status ${done ? 'done' : failed ? 'error' : ''}`}>
                  {failed ? '[FAIL]' : done ? '[READY]' : `[${STATUS_LABEL[doc.status]}]`}
                </span>
                {failed && (
                  <button className="secondary" onClick={() => void onReprocess(doc.id)} title="Re-run extraction from the saved source file">
                    RE-RUN
                  </button>
                )}
                {done && (
                  <button className="secondary" onClick={() => onOpen(doc.id)}>
                    OPEN GRAPH
                  </button>
                )}
                <button className="danger" onClick={() => onDelete(doc.id)} title="Delete">
                  ✕
                </button>
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
