import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph2D from "react-force-graph-2d"
import type { DocumentRecord, GraphData, GraphLink, GraphNode } from '../types'
import * as api from '../api'
import { communityColor, MONO_FONT, tagColor } from '../colors'
import {
  applyFilters,
  connectedComponents,
  distinctRelations,
  endpointId,
  linkConfidence,
  linkDirection,
  linkKind,
  nodeRadius,
  parseStageStats,
  selectGraphView,
  shortestPathIds,
  stageTimingLine,
  stageTimings,
  type Filters,
  type GraphViewMode,
} from '../graphUtils'
import SearchBar from './SearchBar'
import NodePanel from './NodePanel'
import Legend from './Legend'
import FilterBar from './FilterBar'
import PathQuery, { type PathResult } from './PathQuery'
import ExportBar from './ExportBar'

interface Props {
  docId: string
  onBack: () => void
}

interface FGNode extends GraphNode {
  x?: number
  y?: number
}

type FGLink = Omit<GraphLink, 'source' | 'target'> & { source: string | FGNode; target: string | FGNode }

function nodeTooltip(n: FGNode): string {
  return `<div class="fg-tip"><b>${n.name}</b><br/>type: ${n.type} · degree: ${n.degree} · community: ${n.community}</div>`
}

function linkTooltip(l: FGLink): string {
  const s = typeof l.source === 'string' ? l.source : l.source.name
  const t = typeof l.target === 'string' ? l.target : l.target.name
  const provenance = (l.provenance ?? [l.tag]).join(' + ')
  const confidence = Math.round(linkConfidence(l) * 100)
  const arrow = linkDirection(l) === 'undirected' ? '↔' : '→'
  return `<div class="fg-tip">${s} —<i>${l.relation}</i>${arrow} ${t}<br/>${linkKind(l)} · ${provenance} · weight ${l.weight} · confidence ${confidence}%</div>`
}

type PhysicsNode = FGNode & { vx?: number; vy?: number }

function createCommunityForce() {
  let forceNodes: PhysicsNode[] = []
  const force = (alpha: number) => {
    const communities = [...new Set(forceNodes.map((node) => node.community))].sort((a, b) => a - b)
    if (communities.length <= 1 || forceNodes.length <= 4) return
    const radius = 190 + Math.sqrt(forceNodes.length) * 7
    for (const node of forceNodes) {
      const index = communities.indexOf(node.community)
      const angle = -Math.PI / 2 + (index / communities.length) * Math.PI * 2
      const targetX = Math.cos(angle) * radius
      const targetY = Math.sin(angle) * radius
      node.vx = (node.vx ?? 0) + ((targetX - (node.x ?? 0)) * alpha * 0.028)
      node.vy = (node.vy ?? 0) + ((targetY - (node.y ?? 0)) * alpha * 0.028)
    }
  }
  force.initialize = (nodes: PhysicsNode[]) => {
    forceNodes = nodes
  }
  return force
}

export default function GraphView({ docId, onBack }: Props) {
  const [record, setRecord] = useState<DocumentRecord | null>(null)
  const [graph, setGraph] = useState<GraphData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [selected, setSelected] = useState<GraphNode | null>(null)
  const [hovered, setHovered] = useState<FGNode | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filters, setFilters] = useState<Filters>({
    tags: new Set(['llm', 'cooccurrence', 'both']),
    relations: new Set<string>(),
    kinds: new Set(['assertion', 'association']),
    minWeight: 2,
    minConfidence: 0,
  })
  const [path, setPath] = useState<PathResult | null>(null)
  const [pathHops, setPathHops] = useState<number | null>(null)
  const [viewMode, setViewMode] = useState<GraphViewMode>('core')
  const [focusComponentId, setFocusComponentId] = useState<string | null>(null)

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(undefined)
  const relationsInit = useRef(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ width: 800, height: 600 })
  const didFit = useRef(false)
  const forcesConfigured = useRef(false)

  // Load document + graph (poll status until ready)
  useEffect(() => {
    let alive = true
    didFit.current = false
    relationsInit.current = false
    setError(null)
    setSelected(null)
    setPath(null)
    setPathHops(null)
    setSearchQuery('')
    setViewMode('core')
    setFocusComponentId(null)
    async function load() {
      try {
        let rec = await api.getStatus(docId)
        while (alive && rec.status !== 'done' && rec.status !== 'error') {
          await new Promise((r) => setTimeout(r, 1200))
          rec = await api.getStatus(docId)
        }
        if (!alive) return
        setRecord(rec)
        if (rec.status === 'done') {
          setGraph(await api.getGraph(docId))
        } else {
          setError(rec.error ?? 'Processing failed.')
        }
      } catch (e) {
        if (alive) setError(String(e))
      }
    }
    void load()
    return () => {
      alive = false
    }
  }, [docId])

  // Track canvas size
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const r = entries[0].contentRect
      setSize({ width: r.width, height: r.height })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const relationsList = useMemo(() => (graph ? distinctRelations(graph.links) : []), [graph])
  const maxWeight = useMemo(
    () => (graph ? graph.links.reduce((m, l) => Math.max(m, l.weight), 1) : 1),
    [graph],
  )

  // Once the graph loads, select all relations by default (once only — the user
  // may intentionally uncheck every relation, which must not re-populate).
  useEffect(() => {
    if (graph && !relationsInit.current && relationsList.length > 0) {
      relationsInit.current = true
      const associationCount = graph.links.filter((link) => linkKind(link) === 'association').length
      const suggestedMinWeight = associationCount > 100 ? 10 : 2
      setFilters((f) => ({
        ...f,
        relations: new Set(relationsList.map((r) => r.relation)),
        minWeight: Math.max(f.minWeight, suggestedMinWeight),
      }))
    }
  }, [graph, relationsList])

  const filtered = useMemo(
    () => (graph ? applyFilters(graph.nodes, graph.links, filters) : { nodes: [], links: [] }),
    [graph, filters],
  )

  const components = useMemo(
    () => connectedComponents(filtered.nodes, filtered.links),
    [filtered],
  )

  const visible = useMemo(
    () => selectGraphView(filtered.nodes, filtered.links, viewMode, focusComponentId),
    [filtered, viewMode, focusComponentId],
  )

  const selectedNeighborIds = useMemo(() => {
    if (!selected || !graph) return new Set<string>()
    const ids = new Set<string>()
    for (const link of graph.links) {
      const source = endpointId(link.source as unknown as string)
      const target = endpointId(link.target as unknown as string)
      if (source === selected.id) ids.add(target)
      if (target === selected.id) ids.add(source)
    }
    return ids
  }, [graph, selected])

  const searchMatches = useMemo(() => {
    if (!graph || !searchQuery.trim()) return new Set<string>()
    const q = searchQuery.trim().toLowerCase()
    return new Set(graph.nodes.filter((n) => n.name.toLowerCase().includes(q)).map((n) => n.id))
  }, [graph, searchQuery])

  // Zoom to the first search match. Searching a peripheral concept reveals its
  // component instead of leaving the user centered on a hidden node.
  useEffect(() => {
    if (!searchQuery || !graph || searchMatches.size === 0) return
    const first = [...graph.nodes]
      .filter((node) => searchMatches.has(node.id))
      .sort((a, b) => b.degree - a.degree || b.count - a.count || a.name.localeCompare(b.name))[0] as FGNode | undefined
    if (!first) return

    if (!visible.nodes.some((node) => node.id === first.id)) {
      const component = components.find((candidate) => candidate.nodeIds.includes(first.id))
      if (component) {
        setViewMode('component')
        setFocusComponentId(component.id)
      }
      return
    }

    const positioned = graphRef.current?.graphData?.().nodes.find((node: FGNode) => node.id === first.id) as FGNode | undefined
    if (positioned && positioned.x != null && positioned.y != null) {
      graphRef.current.centerAt(positioned.x, positioned.y, 500)
      graphRef.current.zoom(Math.max(1.6, graphRef.current.zoom()), 500)
    }
  }, [searchQuery, searchMatches, graph, components, visible.nodes])

  const graphData = useMemo(() => {
    const seedRadius = Math.max(45, Math.sqrt(Math.max(1, visible.nodes.length)) * 40)
    const seededNodes = visible.nodes.map((node, index) => {
      const angle = (index / Math.max(1, visible.nodes.length)) * Math.PI * 2
      return { ...node, x: Math.cos(angle) * seedRadius, y: Math.sin(angle) * seedRadius, vx: 0, vy: 0 }
    })
    const seededLinks = visible.links.map((link) => ({ ...link }))
    return { nodes: seededNodes as FGNode[], links: seededLinks as FGLink[] }
  }, [visible])

  const labelIds = useMemo(() => {
    const ids = new Set<string>()
    const labelLimit = viewMode === 'all' ? 8 : 12
    for (const node of [...visible.nodes]
      .sort((a, b) => b.degree - a.degree || b.count - a.count || a.name.localeCompare(b.name))
      .slice(0, labelLimit)) {
      ids.add(node.id)
    }
    for (const id of selectedNeighborIds) ids.add(id)
    for (const id of searchMatches) ids.add(id)
    for (const id of path?.nodes ?? []) ids.add(id)
    if (selected) ids.add(selected.id)
    return ids
  }, [visible.nodes, viewMode, selectedNeighborIds, searchMatches, path, selected])

  const linkCurvatures = useMemo(() => {
    const groups = new Map<string, GraphLink[]>()
    for (const link of visible.links) {
      const source = endpointId(link.source as unknown as string)
      const target = endpointId(link.target as unknown as string)
      const key = [source, target].sort().join('|')
      const group = groups.get(key) ?? []
      group.push(link)
      groups.set(key, group)
    }
    const curvatures = new Map<string, number>()
    for (const group of groups.values()) {
      group.forEach((link, index) => {
        curvatures.set(link.id, group.length === 1 ? 0 : (index - (group.length - 1) / 2) * 0.22)
      })
    }
    return curvatures
  }, [visible.links])

  const pathNodes = path?.nodes ?? new Set<string>()
  const pathLinks = path?.links ?? new Set<string>()
  const topConcepts = useMemo(() => {
    if (!graph) return []
    const coreIds = new Set(components.find((component) => component.edgeCount > 0)?.nodeIds ?? graph.nodes.map((node) => node.id))
    return [...graph.nodes]
      .filter((node) => coreIds.has(node.id))
      .sort((a, b) => b.degree - a.degree || b.count - a.count || a.name.localeCompare(b.name))
      .slice(0, 5)
  }, [graph, components])

  const paintNode = useCallback(
    (node: unknown, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const n = node as FGNode
      if (n.x == null || n.y == null) return
      const r = nodeRadius(n) / globalScale
      const isPath = pathNodes.has(n.id)
      const isMatch = searchMatches.has(n.id)
      const isSel = selected?.id === n.id
      const isHov = hovered?.id === n.id
      const isNeighbor = selectedNeighborIds.has(n.id)
      const hasFocus = !!selected
      ctx.globalAlpha = hasFocus && !isSel && !isNeighbor && !isMatch && !isPath ? 0.45 : 1
      ctx.beginPath()
      ctx.arc(n.x, n.y, r, 0, 2 * Math.PI)
      ctx.fillStyle = communityColor(n.community)
      ctx.fill()
      if (isSel || isHov || isPath || isMatch || isNeighbor) {
        ctx.beginPath()
        ctx.arc(n.x, n.y, r + 3 / globalScale, 0, 2 * Math.PI)
        ctx.strokeStyle = isPath ? '#ff2a2a' : isMatch ? '#ffb000' : '#eaeaea'
        ctx.lineWidth = 1.6 / globalScale
        ctx.stroke()
      }
      const showLabel = labelIds.has(n.id) || isSel || isHov || isPath || isMatch || isNeighbor
      if (showLabel) {
        const fontSize = Math.max(9, Math.min(14, r * 1.15))
        const label = n.name.length > 30 ? `${n.name.slice(0, 27)}…` : n.name
        ctx.font = `${fontSize / globalScale}px ${MONO_FONT}`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        const labelY = n.y + r + 4 / globalScale
        const width = ctx.measureText(label).width + 8 / globalScale
        ctx.fillStyle = 'rgba(10, 10, 10, 0.82)'
        ctx.fillRect(n.x - width / 2, labelY - 2 / globalScale, width, fontSize / globalScale + 4 / globalScale)
        ctx.fillStyle = 'rgba(234,234,234,0.96)'
        ctx.fillText(label, n.x, labelY)
      }
      ctx.globalAlpha = 1
    },
    [labelIds, pathNodes, searchMatches, selected?.id, selectedNeighborIds, hovered?.id],
  )

  const paintLink = useCallback(
    (link: unknown, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const l = link as FGLink & { source: FGNode; target: FGNode }
      if (l.source.x == null || l.source.y == null || l.target.x == null || l.target.y == null) return
      const inPath = pathLinks.has(l.id)
      const connected = !!(hovered || selected) && (
        l.source.id === hovered?.id || l.target.id === hovered?.id ||
        l.source.id === selected?.id || l.target.id === selected?.id
      )
      const confidence = linkConfidence(l)
      const assertion = linkKind(l) === 'assertion'
      const curvature = linkCurvatures.get(l.id) ?? 0
      const dx = l.target.x - l.source.x
      const dy = l.target.y - l.source.y
      const distance = Math.max(1, Math.hypot(dx, dy))
      const curveOffset = curvature * Math.min(120, Math.max(56, distance))
      const controlX = (l.source.x + l.target.x) / 2 - (dy / distance) * curveOffset
      const controlY = (l.source.y + l.target.y) / 2 + (dx / distance) * curveOffset
      const hasFocus = !!(selected || hovered)
      const alpha = inPath ? 1 : connected ? 0.96 : hasFocus ? 0.25 : assertion ? 0.72 : 0.14 + confidence * 0.34
      ctx.beginPath()
      ctx.moveTo(l.source.x, l.source.y)
      if (curvature === 0) ctx.lineTo(l.target.x, l.target.y)
      else ctx.quadraticCurveTo(controlX, controlY, l.target.x, l.target.y)
      ctx.strokeStyle = inPath ? '#ff2a2a' : tagColor(l.tag)
      ctx.lineWidth = (inPath ? 3 : connected ? 2.2 : Math.min(3.6, 0.72 + Math.log2(l.weight + 1) * 0.4)) / globalScale
      ctx.globalAlpha = alpha
      ctx.setLineDash(assertion ? [] : [4 / globalScale, 4 / globalScale])
      ctx.stroke()
      ctx.setLineDash([])

      if (linkDirection(l) === 'directed') {
        const tangentX = l.target.x - (curvature === 0 ? l.source.x : controlX)
        const tangentY = l.target.y - (curvature === 0 ? l.source.y : controlY)
        const angle = Math.atan2(tangentY, tangentX)
        const arrowSize = 5.5 / globalScale
        const tipX = l.target.x - Math.cos(angle) * (nodeRadius(l.target) / globalScale + arrowSize * 0.35)
        const tipY = l.target.y - Math.sin(angle) * (nodeRadius(l.target) / globalScale + arrowSize * 0.35)
        ctx.beginPath()
        ctx.moveTo(tipX, tipY)
        ctx.lineTo(tipX - Math.cos(angle - Math.PI / 6) * arrowSize, tipY - Math.sin(angle - Math.PI / 6) * arrowSize)
        ctx.lineTo(tipX - Math.cos(angle + Math.PI / 6) * arrowSize, tipY - Math.sin(angle + Math.PI / 6) * arrowSize)
        ctx.closePath()
        ctx.fillStyle = inPath ? '#ff2a2a' : tagColor(l.tag)
        ctx.fill()
      }
      ctx.globalAlpha = 1
    },
    [linkCurvatures, pathLinks, hovered, selected],
  )

  const handleNodeClick = useCallback((node: unknown) => {
    const next = node as FGNode
    const component = components.find((candidate) => candidate.nodeIds.includes(next.id))
    setSelected(next)
    if (component) {
      setViewMode('component')
      setFocusComponentId(component.id)
    }
    if (next.x != null && next.y != null) {
      graphRef.current?.centerAt(next.x, next.y, 450)
      graphRef.current?.zoom(Math.max(1.5, graphRef.current?.zoom?.() ?? 1), 450)
    }
  }, [components])

  const handlePathResult = useCallback(
    (startId: string, endId: string) => {
      if (!graph) return
      const ids = shortestPathIds(graph.links, startId, endId)
      if (!ids) {
        setPath({ start: startId, end: endId, nodes: new Set(), links: new Set() })
        setPathHops(null)
        return
      }
      const linkIds = new Set<string>()
      for (let i = 0; i < ids.length - 1; i++) {
        const found = graph.links.find(
          (l) => {
            const source = endpointId(l.source as unknown as string)
            const target = endpointId(l.target as unknown as string)
            return (source === ids[i] && target === ids[i + 1]) || (source === ids[i + 1] && target === ids[i])
          },
        )
        if (found) linkIds.add(found.id)
      }
      const component = components.find((candidate) => candidate.nodeIds.includes(ids[0]))
      if (component) {
        setViewMode('component')
        setFocusComponentId(component.id)
      }
      setPath({ start: startId, end: endId, nodes: new Set(ids), links: linkIds })
      setPathHops(ids.length - 1)
    },
    [graph, components],
  )

  const clearPath = useCallback(() => {
    setPath(null)
    setPathHops(null)
  }, [])

  const fitGraph = useCallback((nodeCount: number, nodeFilter?: (node: FGNode) => boolean) => {
    graphRef.current?.zoomToFit(500, 40, nodeFilter)
    window.setTimeout(() => {
      let cap: number | null = null
      if (nodeCount <= 4) cap = 3.5
      else if (nodeCount <= 10) cap = 4.2
      const currentZoom = graphRef.current?.zoom?.()
      if (cap && currentZoom > cap) graphRef.current?.zoom(cap, 250)
    }, 560)
  }, [])

  const fitVisible = useCallback(() => {
    fitGraph(visible.nodes.length)
  }, [fitGraph, visible.nodes.length])

  const fitCore = useCallback(() => {
    const coreIds = new Set(components.find((component) => component.edgeCount > 0)?.nodeIds ?? [])
    if (coreIds.size === 0) {
      fitVisible()
      return
    }
    fitGraph(coreIds.size, (node: FGNode) => coreIds.has(String(node.id)))
  }, [components, fitGraph, fitVisible])

  const resetMap = useCallback(() => {
    setSelected(null)
    setHovered(null)
    setSearchQuery('')
    setPath(null)
    setPathHops(null)
    setViewMode('core')
    setFocusComponentId(null)
  }, [])

  useEffect(() => {
    didFit.current = false
    forcesConfigured.current = false
  }, [graphData])

  const graphStats = graph ? parseStageStats(graph.document.stats) : null
  const graphTimings = graphStats ? stageTimings(graphStats) : []

  if (error) {
    return (
      <div className="graph-view">
        <div className="graph-toolbar">
          <button className="secondary" onClick={onBack}>
            ← Documents
          </button>
          <span className="graph-title">{record?.name ?? '…'}</span>
        </div>
        <div className="graph-empty muted">{error}</div>
      </div>
    )
  }

  return (
    <div className="graph-view">
      <div className="graph-toolbar">
        <button className="secondary" onClick={onBack}>
          ← Documents
        </button>
        <span className="graph-title">{record?.name ?? '…'}</span>
        <span className="flex-spacer" />
        {graph && <ExportBar docId={docId} />}
        {graph && (
          <span className="stat-chip" title={graphTimings.length > 0 ? 'Pipeline stage timings' : undefined}>
            {visible.nodes.length} / {graph.nodes.length} CONCEPTS · {visible.links.length} / {graph.links.length} LINKS
            {graphTimings.length > 0 && (
              <>
                {' · '}
                <span className="stage-times">
                  {stageTimingLine(graphStats)}
                </span>
              </>
            )}
          </span>
        )}
      </div>

      <div className="graph-body">
        <aside className="graph-side">
          {graph && (
            <section className="reading-guide">
              <span className="panel-kicker">Reading guide</span>
              <h2>Follow the statements</h2>
              <p>Start with one concept. Click it to dim everything else and inspect the evidence behind each connection.</p>
              <div className="reading-keys">
                <span><i className="key-line key-solid" /> extracted statement</span>
                <span><i className="key-line key-faint" /> nearby-text association</span>
              </div>
              <div className="quick-picks">
                <span className="quick-picks-label">Start with a central concept</span>
                {topConcepts.map((concept) => (
                  <button className="quick-pick" key={concept.id} onClick={() => handleNodeClick(concept)}>
                    <span>{concept.name}</span>
                    <small>{concept.degree} links</small>
                  </button>
                ))}
              </div>
            </section>
          )}
          {graph && (
            <section className="panel-section map-view-controls">
              <h4>Map view</h4>
              <div className="view-mode-buttons" role="tablist" aria-label="Graph view">
                <button
                  className={viewMode === 'core' ? 'active' : 'secondary'}
                  onClick={() => {
                    setViewMode('core')
                    setFocusComponentId(null)
                  }}
                >
                  Core network
                </button>
                <button
                  className={viewMode === 'component' ? 'active' : 'secondary'}
                  onClick={() => {
                    const component = components.find((candidate) => candidate.edgeCount > 0) ?? components[0]
                    setViewMode('component')
                    setFocusComponentId(component?.id ?? null)
                  }}
                >
                  Selected component
                </button>
                <button
                  className={viewMode === 'all' ? 'active' : 'secondary'}
                  onClick={() => setViewMode('all')}
                >
                  All visible
                </button>
              </div>
              <p className="view-summary">
                {visible.component
                  ? `${visible.component.nodeCount} concepts · ${visible.component.edgeCount} links in view`
                  : `${visible.nodes.length} concepts · ${visible.links.length} links across all visible components`}
              </p>
              <div className="component-list">
                {components.filter((component) => component.edgeCount > 0).slice(0, 6).map((component, index) => (
                  <button
                    className={`component-pick ${visible.component?.id === component.id ? 'selected' : ''}`}
                    key={component.id}
                    onClick={() => {
                      setViewMode('component')
                      setFocusComponentId(component.id)
                      setSelected(null)
                    }}
                  >
                    <span><b>#{index + 1}</b> {component.leadName}</span>
                    <small>{component.nodeCount} concepts · {component.edgeCount} links</small>
                  </button>
                ))}
              </div>
              {components.filter((component) => component.edgeCount > 0).length > 6 && (
                <p className="view-summary">+ {components.filter((component) => component.edgeCount > 0).length - 6} smaller components</p>
              )}
            </section>
          )}
          <SearchBar query={searchQuery} onQuery={setSearchQuery} resultCount={searchMatches.size} />
          <PathQuery
            nodes={graph?.nodes ?? []}
            onResult={handlePathResult}
            onClear={clearPath}
            result={path}
            hops={pathHops}
          />
          {graph && <FilterBar relations={relationsList} filters={filters} onChange={setFilters} maxWeight={maxWeight} />}
          {graph && <Legend communityCount={graph.document.stats.communities ?? 0} />}
        </aside>

        <div className="graph-canvas" ref={containerRef}>
          {graph ? (
            <>
            <div className="canvas-meta">
              <strong>{visible.links.length} visible links</strong>
              <span>·</span>
              <span>{selected ? `focused on ${selected.name}` : viewMode === 'core' ? 'core network' : viewMode === 'all' ? 'all visible components' : 'selected component'}</span>
            </div>
            <div className="canvas-actions" aria-label="Graph canvas controls">
              <button className="secondary tiny" onClick={fitCore}>FIT CORE</button>
              <button className="secondary tiny" onClick={fitVisible}>FIT VISIBLE</button>
              <button className="secondary tiny" onClick={resetMap}>RESET MAP</button>
            </div>
            <ForceGraph2D
              ref={graphRef}
              width={size.width}
              height={size.height}
              graphData={graphData}
              backgroundColor="#0a0a0a"
              nodeVal={(n: unknown) => nodeRadius(n as FGNode)}
              nodeLabel={(n: unknown) => nodeTooltip(n as FGNode)}
              linkLabel={(l: unknown) => linkTooltip(l as FGLink)}
              nodeCanvasObjectMode={() => 'replace'}
              nodeCanvasObject={paintNode}
              linkCanvasObjectMode={() => 'replace'}
              linkCanvasObject={paintLink}
              onNodeClick={handleNodeClick}
              onNodeHover={(n: unknown) => setHovered((n as FGNode) ?? null)}
              onEngineStop={() => {
                const charge = graphRef.current?.d3Force('charge')
                const linkForce = graphRef.current?.d3Force('link')
                const center = graphRef.current?.d3Force('center')
                if (!forcesConfigured.current) {
                  charge?.strength(-280)
                  linkForce?.distance((link: FGLink) => {
                    if (linkKind(link) === 'assertion') return 98
                    return 72 + Math.max(0, 10 - Math.min(link.weight, 10)) * 2
                  })
                  center?.strength?.(0.65)
                  graphRef.current?.d3Force('community', createCommunityForce())
                  forcesConfigured.current = true
                  graphRef.current?.d3ReheatSimulation()
                  return
                }
                if (!didFit.current) {
                  didFit.current = true
                  fitGraph(visible.nodes.length)
                }
              }}
              d3VelocityDecay={0.36}
              d3AlphaDecay={0.035}
              warmupTicks={120}
              cooldownTicks={220}
            />
            </>
          ) : (
            <div className="graph-empty">Building graph…</div>
          )}
        </div>

        {selected && graph && <NodePanel node={selected} graph={graph} onClose={() => setSelected(null)} />}
      </div>
    </div>
  )
}
