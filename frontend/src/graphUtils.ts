import type { EdgeDirection, EdgeKind, GraphEvidence, GraphLink, GraphNode } from './types'

export interface Filters {
  tags: Set<string>
  relations: Set<string>
  kinds: Set<EdgeKind>
  minWeight: number
  minConfidence: number
}

export function linkDirection(link: Pick<GraphLink, 'direction' | 'kind' | 'tag'>): EdgeDirection {
  return link.direction ?? (link.kind === 'association' || link.tag === 'cooccurrence' ? 'undirected' : 'directed')
}

export function linkKind(link: Pick<GraphLink, 'direction' | 'kind' | 'tag'>): EdgeKind {
  return link.kind ?? (linkDirection(link) === 'undirected' ? 'association' : 'assertion')
}

export function linkConfidence(link: Pick<GraphLink, 'quality'>): number {
  return link.quality?.confidence ?? 0
}

function matchesTag(link: GraphLink, tags: Set<string>): boolean {
  if (tags.has(link.tag)) return true
  // A mixed edge is visible when either of its contributing provenances is
  // selected, while retaining the explicit BOTH toggle for auditability.
  return link.tag === 'both' && (tags.has('llm') || tags.has('cooccurrence'))
}

/** force-graph mutates links to reference node objects — handle both forms. */
export function endpointId(x: string | { id: string }): string {
  return typeof x === 'string' ? x : x.id
}

export type GraphViewMode = 'core' | 'component' | 'all'

export interface GraphComponent {
  id: string
  nodeIds: string[]
  nodeCount: number
  edgeCount: number
  signal: number
  totalWeight: number
  leadNodeId: string
  leadName: string
}

function edgeSignal(link: GraphLink): number {
  const confidence = linkConfidence(link)
  const weight = Math.max(1, link.weight || 1)
  const semanticBoost = linkKind(link) === 'assertion' ? 2 : 1
  return semanticBoost * (0.5 + confidence) * Math.log2(weight + 1)
}

/** Rank undirected connected components by the quality of the visible network. */
export function connectedComponents(nodes: GraphNode[], links: GraphLink[]): GraphComponent[] {
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const adjacency = new Map<string, Set<string>>()
  for (const node of nodes) adjacency.set(node.id, new Set())

  for (const link of links) {
    const source = endpointId(link.source as unknown as string)
    const target = endpointId(link.target as unknown as string)
    if (!adjacency.has(source) || !adjacency.has(target) || source === target) continue
    adjacency.get(source)!.add(target)
    adjacency.get(target)!.add(source)
  }

  const seen = new Set<string>()
  const raw: Array<{ nodeIds: string[]; links: GraphLink[] }> = []
  for (const node of nodes) {
    if (seen.has(node.id)) continue
    const nodeIds: string[] = []
    const queue = [node.id]
    seen.add(node.id)
    while (queue.length > 0) {
      const current = queue.shift()!
      nodeIds.push(current)
      for (const next of adjacency.get(current) ?? []) {
        if (!seen.has(next)) {
          seen.add(next)
          queue.push(next)
        }
      }
    }
    const members = new Set(nodeIds)
    raw.push({
      nodeIds,
      links: links.filter((link) => {
        const source = endpointId(link.source as unknown as string)
        const target = endpointId(link.target as unknown as string)
        return members.has(source) && members.has(target)
      }),
    })
  }

  return raw
    .map(({ nodeIds, links: componentLinks }) => {
      const orderedNodes = nodeIds
        .map((id) => byId.get(id))
        .filter((node): node is GraphNode => node !== undefined)
        .sort((a, b) => b.degree - a.degree || b.count - a.count || a.name.localeCompare(b.name))
      const sortedIds = orderedNodes.map((node) => node.id)
      const componentId = [...nodeIds].sort()[0] ?? nodeIds[0]
      const lead = orderedNodes[0]
      return {
        id: componentId,
        nodeIds: sortedIds,
        nodeCount: sortedIds.length,
        edgeCount: componentLinks.length,
        signal: componentLinks.reduce((total, link) => total + edgeSignal(link), 0),
        totalWeight: componentLinks.reduce((total, link) => total + (link.weight || 0), 0),
        leadNodeId: lead?.id ?? nodeIds[0],
        leadName: lead?.name ?? nodeIds[0],
      }
    })
    .sort(
      (a, b) =>
        b.signal - a.signal ||
        b.nodeCount - a.nodeCount ||
        b.edgeCount - a.edgeCount ||
        a.leadName.localeCompare(b.leadName),
    )
}

export function selectGraphView(
  nodes: GraphNode[],
  links: GraphLink[],
  mode: GraphViewMode,
  componentId?: string | null,
): { nodes: GraphNode[]; links: GraphLink[]; component?: GraphComponent } {
  if (mode === 'all') return { nodes, links }

  const components = connectedComponents(nodes, links)
  const component =
    (mode === 'component' && componentId
      ? components.find((candidate) => candidate.id === componentId)
      : undefined) ?? components.find((candidate) => candidate.edgeCount > 0) ?? components[0]
  if (!component) return { nodes, links }

  const keep = new Set(component.nodeIds)
  return {
    nodes: nodes.filter((node) => keep.has(node.id)),
    links: links.filter((link) => {
      const source = endpointId(link.source as unknown as string)
      const target = endpointId(link.target as unknown as string)
      return keep.has(source) && keep.has(target)
    }),
    component,
  }
}

export function nodeRadius(d: { degree?: number; count?: number }): number {
  const degree = Math.max(0, d.degree ?? 0)
  const mentions = Math.max(0, d.count ?? 0)
  return Math.max(4, Math.min(16, Math.sqrt(degree * 1.4 + Math.log2(mentions + 1) * 2 + 1) * 2.1))
}

export function applyFilters(nodes: GraphNode[], links: GraphLink[], filters: Filters) {
  const filteredLinks = links.filter((l) => {
    const kind = linkKind(l)
    // Typed assertions are already a deliberate statement, so the inferred
    // weight threshold only controls co-occurrence noise.
    const meetsWeight = kind === 'assertion' || l.weight >= filters.minWeight
    return (
      matchesTag(l, filters.tags) &&
      filters.relations.has(l.relation) &&
      filters.kinds.has(kind) &&
      meetsWeight &&
      linkConfidence(l) >= filters.minConfidence
    )
  })
  // Keep isolated nodes visible so every detected community remains represented
  // in the graph and its legend. They are valid graph nodes even when no edge
  // matches the active relation/tag filters.
  return { nodes, links: filteredLinks }
}

export function distinctRelations(links: GraphLink[]): { relation: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const l of links) counts.set(l.relation, (counts.get(l.relation) ?? 0) + 1)
  return [...counts.entries()]
    .map(([relation, count]) => ({ relation, count }))
    .sort((a, b) => b.count - a.count)
}

// ── pipeline stage timing breakdown ─────────────────────────────────
// The backend already records per-stage seconds (parsing_seconds,
// llm_seconds, pipeline_seconds, …) in both `DocumentRecord.stats_json`
// (JSON string) and `graph.document.stats` (object). These helpers turn
// either shape into a small typed breakdown for display.

export interface StageStats {
  parsingSeconds?: number
  chunkingSeconds?: number
  statisticalSeconds?: number
  llmSeconds?: number
  pipelineSeconds?: number
  chunks?: number
  llmSelectedChunks?: number
  llmChunks?: number
  llmConcurrency?: number
  llmUsed?: boolean
}

export interface StageTiming {
  label: string
  seconds: number
}

/** Parse a stats source (JSON string or object) into a typed breakdown, or null. */
export function parseStageStats(
  raw: string | null | undefined | Record<string, number>,
): StageStats | null {
  if (!raw) return null
  let data: Record<string, number> | null = null
  if (typeof raw === 'string') {
    try {
      data = JSON.parse(raw) as Record<string, number>
    } catch {
      return null
    }
  } else if (typeof raw === 'object') {
    data = raw
  }
  if (!data) return null
  const num = (k: string): number | undefined => {
    const v = data[k]
    return typeof v === 'number' && Number.isFinite(v) ? v : undefined
  }
  const llmSeconds = num('llm_seconds')
  const llmSelectedChunks = num('llm_selected_chunks')
  const llmChunks = num('llm_chunks')
  const hasAny = ['parsing_seconds', 'chunking_seconds', 'statistical_seconds', 'llm_seconds', 'pipeline_seconds'].some(
    (k) => num(k) !== undefined,
  )
  if (!hasAny) return null
  return {
    parsingSeconds: num('parsing_seconds'),
    chunkingSeconds: num('chunking_seconds'),
    statisticalSeconds: num('statistical_seconds'),
    llmSeconds,
    pipelineSeconds: num('pipeline_seconds'),
    chunks: num('chunks'),
    llmSelectedChunks,
    llmChunks,
    llmConcurrency: num('llm_concurrency'),
    llmUsed: (llmSeconds ?? 0) > 0 || (llmChunks ?? 0) > 0,
  }
}

/** Ordered, present-only stage timings for display (parse · llm · total). */
export function stageTimings(stats: StageStats): StageTiming[] {
  const out: StageTiming[] = []
  if (stats.parsingSeconds !== undefined) out.push({ label: 'parse', seconds: stats.parsingSeconds })
  if (stats.chunkingSeconds !== undefined) out.push({ label: 'chunk', seconds: stats.chunkingSeconds })
  if (stats.statisticalSeconds !== undefined) out.push({ label: 'statistical', seconds: stats.statisticalSeconds })
  if (stats.llmUsed && stats.llmSeconds !== undefined) out.push({ label: 'llm', seconds: stats.llmSeconds })
  if (stats.pipelineSeconds !== undefined) out.push({ label: 'total', seconds: stats.pipelineSeconds })
  return out
}

/** Human duration: 2.1s · 3m 12s · 1h 05m. */
export function formatDuration(seconds: number | undefined | null): string {
  if (seconds === undefined || seconds === null || !Number.isFinite(seconds)) return '—'
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60)
    const s = Math.round(seconds % 60)
    return `${m}m ${s}s`
  }
  const h = Math.floor(seconds / 3600)
  const m = Math.round((seconds % 3600) / 60)
  return `${h}h ${String(m).padStart(2, '0')}m`
}

/** One-line stage timing breakdown, e.g. "parse 2.1s · llm 3m 12s · total 3m 20s". */
export function stageTimingLine(stats: StageStats | null): string {
  if (!stats) return ''
  return stageTimings(stats)
    .map((t) => `${t.label} ${formatDuration(t.seconds)}`)
    .join(' · ')
}

export interface NeighborRow {
  id: string
  name: string
  relation: string
  originalRelation?: string
  direction: 'out' | 'in' | 'both'
  edgeDirection: EdgeDirection
  kind: EdgeKind
  tag: string
  weight: number
  confidence: number
  evidence: GraphEvidence[]
  snippet?: string
}

export function neighbors(nodeId: string, nodes: GraphNode[], links: GraphLink[]): NeighborRow[] {
  const byId = new Map(nodes.map((n) => [n.id, n]))
  const rows: NeighborRow[] = []
  for (const l of links) {
    const s = endpointId(l.source as unknown as string)
    const t = endpointId(l.target as unknown as string)
    const edgeDirection = linkDirection(l)
    if (s === nodeId) {
      const n = byId.get(t)
      if (n) {
        rows.push({
          id: n.id,
          name: n.name,
          relation: l.relation,
          originalRelation: l.original_relation,
          direction: edgeDirection === 'undirected' ? 'both' : 'out',
          edgeDirection,
          kind: linkKind(l),
          tag: l.tag,
          weight: l.weight,
          confidence: linkConfidence(l),
          evidence: l.evidence ?? [],
          snippet: l.snippet,
        })
      }
    } else if (t === nodeId) {
      const n = byId.get(s)
      if (n) {
        rows.push({
          id: n.id,
          name: n.name,
          relation: l.relation,
          originalRelation: l.original_relation,
          direction: edgeDirection === 'undirected' ? 'both' : 'in',
          edgeDirection,
          kind: linkKind(l),
          tag: l.tag,
          weight: l.weight,
          confidence: linkConfidence(l),
          evidence: l.evidence ?? [],
          snippet: l.snippet,
        })
      }
    }
  }
  return rows.sort(
    (a, b) =>
      Number(b.kind === 'assertion') - Number(a.kind === 'assertion') ||
      b.confidence - a.confidence ||
      b.weight - a.weight ||
      a.name.localeCompare(b.name),
  )
}

export function shortestPathIds(
  links: GraphLink[],
  startId: string,
  endId: string,
): string[] | null {
  if (startId === endId) return [startId]
  const adj = new Map<string, string[]>()
  const add = (a: string, b: string) => {
    if (!adj.has(a)) adj.set(a, [])
    adj.get(a)!.push(b)
  }
  for (const l of links) {
    const s = endpointId(l.source as unknown as string)
    const t = endpointId(l.target as unknown as string)
    add(s, t)
    add(t, s)
  }
  const prev = new Map<string, string | null>([[startId, null]])
  const queue = [startId]
  while (queue.length) {
    const cur = queue.shift()!
    if (cur === endId) break
    for (const nxt of adj.get(cur) ?? []) {
      if (!prev.has(nxt)) {
        prev.set(nxt, cur)
        queue.push(nxt)
      }
    }
  }
  if (!prev.has(endId)) return null
  const path: string[] = []
  let cur: string | null = endId
  while (cur) {
    path.push(cur)
    cur = prev.get(cur) ?? null
  }
  return path.reverse()
}
