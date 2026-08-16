/**
 * Industrial CRT color system (Tactical Telemetry archetype).
 * System accent = hazard red. Terminal green is RESERVED for the single
 * READY status indicator — never use it for data encoding here.
 */
export const COMMUNITY_PALETTE = [
  '#eaeaea', // phosphor white
  '#ff2a2a', // hazard red
  '#ffb000', // amber
  '#2de2e6', // cyan
  '#7aa2ff', // blue
  '#c792ea', // violet
  '#ff9e64', // orange
  '#e0af68', // brass
  '#7dcfff', // ice blue
  '#bb9af7', // lavender
  '#f7768e', // signal pink
  '#b8c0e0', // steel
]

export function communityColor(community: number): string {
  return COMMUNITY_PALETTE[((community % COMMUNITY_PALETTE.length) + COMMUNITY_PALETTE.length) % COMMUNITY_PALETTE.length]
}

/** Edge provenance encoding: extracted = bright, inferred = dim, mixed = amber. */
export const TAG_COLORS: Record<string, string> = {
  llm: '#eaeaea',
  cooccurrence: '#5c6370',
  both: '#ffb000',
}

export function tagColor(tag: string): string {
  return TAG_COLORS[tag] ?? '#5c6370'
}

export const TAG_LABELS: Record<string, string> = {
  llm: 'LLM EXTRACTED',
  cooccurrence: 'CO-OCCURRENCE',
  both: 'LLM + CO-OCCURRENCE',
}

export const MONO_FONT = "'JetBrains Mono', 'IBM Plex Mono', Consolas, monospace"
