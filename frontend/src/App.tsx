import { useCallback, useEffect, useRef, useState } from 'react'
import type { AppConfig, DocumentRecord } from './types'
import * as api from './api'
import UploadPage from './components/UploadPage'
import DocumentList from './components/DocumentList'
import GraphView from './components/GraphView'

export type View =
  | { name: 'list' }
  | { name: 'graph'; docId: string }

const POLL_BASE_MS = 1500
const POLL_MAX_MS = 15_000

export default function App() {
  const [view, setView] = useState<View>({ name: 'list' })
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [documents, setDocuments] = useState<DocumentRecord[]>([])
  const [error, setError] = useState<string | null>(null)
  const [backendOnline, setBackendOnline] = useState(true)

  const configRef = useRef<AppConfig | null>(null)
  const backoffRef = useRef(POLL_BASE_MS)
  // Mirror backendOnline into a ref so the poll loop can read the latest value
  // without re-subscribing (the loop runs forever by design).
  const backendOnlineRef = useRef(backendOnline)
  useEffect(() => {
    backendOnlineRef.current = backendOnline
  }, [backendOnline])

  const refreshDocs = useCallback(async () => {
    setDocuments(await api.listDocuments())
  }, [])

  // Poll loop: keeps the document list fresh while any job is running and
  // self-heals when the backend is down. A failed poll is NOT surfaced as a
  // permanent error banner — the backend may be restarting. We back off,
  // keep polling, and only show the persistent banner for real API errors.
  useEffect(() => {
    let stopped = false
    let timer: number

    const tick = async () => {
      if (stopped) return
      try {
        const docs = await api.listDocuments()
        backoffRef.current = POLL_BASE_MS
        if (!backendOnlineRef.current) {
          setBackendOnline(true)
          // Freshly back online: (re)load config for the LLM badge.
          try {
            const cfg = await api.getConfig()
            configRef.current = cfg
            setConfig(cfg)
          } catch {
            /* non-fatal; retried on a later tick */
          }
        }
        setDocuments(docs)
      } catch (e) {
        if (api.isNetworkError(e)) {
          setBackendOnline(false)
          backoffRef.current = Math.min(backoffRef.current * 2, POLL_MAX_MS)
        } else {
          setError(String(e))
        }
      }
      timer = window.setTimeout(tick, backoffRef.current)
    }

    // First tick: load config if we don't have it yet.
    const boot = async () => {
      if (configRef.current === null) {
        try {
          const cfg = await api.getConfig()
          configRef.current = cfg
          setConfig(cfg)
        } catch {
          /* handled by the poll loop below */
        }
      }
      timer = window.setTimeout(tick, 250)
    }
    void boot()

    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
  }, [])

  const onUpload = useCallback(
    async (file: File, mode: 'fast' | 'balanced' | 'full') => {
      setError(null)
      try {
        await api.uploadDocument(file, mode)
        await refreshDocs()
      } catch (e) {
        setError(String(e))
      }
    },
    [refreshDocs],
  )

  const onReprocess = useCallback(
    async (id: string) => {
      setError(null)
      try {
        await api.reprocessDocument(id)
        await refreshDocs()
      } catch (e) {
        setError(String(e))
      }
    },
    [refreshDocs],
  )

  const onDelete = useCallback(
    async (id: string) => {
      setError(null)
      try {
        await api.deleteDocument(id)
        await refreshDocs()
      } catch (e) {
        setError(String(e))
      }
    },
    [refreshDocs],
  )

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand" onClick={() => setView({ name: 'list' })} role="button" tabIndex={0}>
          <span className="brand-name">DocGraph by Juan Mackie</span>
        </div>
        <div className="header-right">
          {config && (
            <span className={`llm-badge ${config.has_api_key ? 'on' : 'off'}`}>
              {config.has_api_key
                ? `LLM LINK ONLINE · ${config.model}`
                : 'LLM LINK OFFLINE · STAT MODE'}
            </span>
          )}
          <span className="sys-ver">SYS v0.1.0</span>
        </div>
      </header>

      {!backendOnline && (
        <div className="banner warn">
          BACKEND OFFLINE — RECONNECTING… <span className="banner-close">⟳</span>
        </div>
      )}

      {error && (
        <div className="banner error" onClick={() => setError(null)} role="button">
          {error} <span className="banner-close">✕</span>
        </div>
      )}

      {view.name === 'list' && config && !config.has_api_key && (
        <div className="banner info">
          <strong>LLM LINK OFFLINE.</strong> No API key configured — relationships come from
          keyword co-occurrence. Set <code>OPENAI_API_KEY</code> (or point{' '}
          <code>OPENAI_BASE_URL</code> at Ollama / LM Studio) in <code>.env</code> and re-upload
          for richer, typed relationships.
        </div>
      )}

      {view.name === 'list' ? (
        <main className="page">
          <UploadPage onUpload={onUpload} />
          <DocumentList
            documents={documents}
            onOpen={(id) => setView({ name: 'graph', docId: id })}
            onDelete={onDelete}
            onReprocess={onReprocess}
          />
        </main>
      ) : (
        <GraphView docId={view.docId} onBack={() => setView({ name: 'list' })} />
      )}
    </div>
  )
}
