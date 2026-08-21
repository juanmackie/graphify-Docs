import type { AppConfig, DocumentRecord, GraphData } from './types'

const API = '/api'
const FETCH_TIMEOUT_MS = 20_000

/** Network-level failure (backend down, connection dropped, request timed out).
 *  Distinct from an HTTP error response, which carries a server `detail`. */
export class NetworkError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'NetworkError'
  }
}

export function isNetworkError(e: unknown): boolean {
  return e instanceof TypeError || e instanceof NetworkError
}

async function fetchJson(path: string, init?: RequestInit): Promise<Response> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS)
  try {
    return await fetch(`${API}${path}`, { ...init, signal: controller.signal })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new NetworkError(`Request timed out after ${FETCH_TIMEOUT_MS / 1000}s`)
    }
    throw e // TypeError("Failed to fetch") — backend unreachable / connection dropped
  } finally {
    window.clearTimeout(timer)
  }
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(detail || `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export async function getHealth(): Promise<{ ok: boolean }> {
  return json(await fetchJson('/health'))
}

export async function getConfig(): Promise<AppConfig> {
  return json(await fetchJson('/config'))
}

export async function listDocuments(): Promise<DocumentRecord[]> {
  return json(await fetchJson('/documents'))
}

export async function uploadDocument(
  file: File,
  mode: 'fast' | 'balanced' | 'full' = 'balanced',
): Promise<{ doc_id: string; name: string }> {
  const form = new FormData()
  form.append('file', file)
  form.append('mode', mode)
  const res = await fetchJson('/documents', { method: 'POST', body: form })
  return json(res)
}

export async function reprocessDocument(id: string): Promise<{ doc_id: string; status: string }> {
  return json(await fetchJson(`/documents/${id}/reprocess`, { method: 'POST' }))
}

export async function getStatus(id: string): Promise<DocumentRecord> {
  return json(await fetchJson(`/documents/${id}/status`))
}

export async function getGraph(id: string): Promise<GraphData> {
  return json(await fetchJson(`/documents/${id}/graph`))
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await fetchJson(`/documents/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`${res.status}`)
}

export function exportUrl(id: string, kind: 'html' | 'report' | 'csv'): string {
  return `${API}/documents/${id}/export/${kind}`
}

/** Trigger a browser download for a GET export endpoint. */
export function downloadExport(id: string, kind: 'html' | 'report' | 'csv'): void {
  window.location.href = exportUrl(id, kind)
}
