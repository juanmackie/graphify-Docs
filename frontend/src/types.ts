export interface DocumentRecord {
  id: string
  name: string
  ext: string
  size: number
  status: 'queued' | 'parsing' | 'chunking' | 'extracting' | 'clustering' | 'done' | 'error'
  extraction_mode?: 'fast' | 'balanced' | 'full'
  progress_detail?: string | null
  progress: number
  error?: string | null
  node_count: number
  edge_count: number
  stats_json?: string | null
  created_at: string
  updated_at: string
}

export interface GraphNode {
  id: string
  name: string
  type: string
  snippet?: string
  degree: number
  community: number
  sources: string[]
  count: number
}

export type EdgeTag = 'llm' | 'cooccurrence' | 'both'
export type EdgeDirection = 'directed' | 'undirected'
export type EdgeKind = 'assertion' | 'association'

export interface GraphEvidence {
  text: string
  source?: string
  chunk_index?: number
  paragraph_index?: number
  sentence_index?: number
}

export interface LinkQuality {
  score: number
  confidence: number
  support_count: number
  endpoint_support: number
  evidence_count: number
  reasons: string[]
}

export interface GraphLink {
  id: string
  source: string
  target: string
  relation: string
  relation_key?: string
  original_relation?: string
  relation_aliases?: string[]
  direction?: EdgeDirection
  kind?: EdgeKind
  tag: EdgeTag
  provenance?: string[]
  weight: number
  snippet?: string
  evidence?: GraphEvidence[]
  quality?: LinkQuality
}

export interface GraphData {
  document: {
    id: string
    name: string
    stats: Record<string, number>
    llm_enabled: boolean
    created_at: string
    schema_version?: number
    relation_schema_version?: number
  }
  nodes: GraphNode[]
  links: GraphLink[]
}

export interface AppConfig {
  has_api_key: boolean
  model: string
  extraction_mode?: 'fast' | 'balanced' | 'full'
  extraction_modes?: Array<'fast' | 'balanced' | 'full'>
  llm_concurrency?: number
}
