# Frontend AGENTS.md

## Purpose

React + Vite + TypeScript single-page app: upload documents, render the knowledge graph (force-directed), search/filter/path queries, and trigger exports. The production build (`dist/`) is served by FastAPI at `/` — one process, one port.

## Ownership

- `src/App.tsx` — routing between document list/upload and graph view
- `src/api.ts` — typed fetch client (20s timeout, `NetworkError` distinct from HTTP errors)
- `src/types.ts` — `DocumentRecord`, `GraphData`, `GraphNode`, `GraphLink`, `AppConfig`
- `src/graphUtils.ts` — filtering, neighbors, shortest path, stage-timing helpers
- `src/colors.ts`, `src/styles.css` — dark "phosphor" theme, CSS variables (`--mono`, `--text-dim`, …)
- `src/main.tsx`, `index.html`, `package.json`, `tsconfig.json`, `vite.config.ts`

## Local Contracts

- **Scripts**: `npm run dev` (Vite on :5173, proxies `/api` → `http://localhost:8000`); `npm run build` = `tsc && vite build` → `dist/`; `npm run preview`.
- **API types mirror the backend JSON** — keep `DocumentRecord` in sync with the sqlite row (includes `stats_json?: string | null`; stage timings parsed via `graphUtils.parseStageStats` / rendered by `formatDuration` + `stageTimings`). Graph links preserve legacy fields and may include schema-v2 `relation_key`, original labels, direction/kind, provenance, evidence, and quality/confidence metadata.
- **No frontend test runner** — verification is the type-checked build plus manual E2E; use `react-dom/server` + esbuild for throwaway render smoke tests when component logic changes. `graphUtils.applyFilters` must keep legacy links readable while filtering provenance, relation kind, weight, and confidence.
- **Graph readability views** — `graphUtils.connectedComponents` ranks the currently visible network, `selectGraphView` powers the default core-network view, selected-component focus, and all-visible view. These are display scopes only; the full graph remains available through search, filters, and the all-visible mode.
- **Export links** come from `api.exportUrl` / `api.downloadExport` — never hardcode export paths.
- Production must not depend on the dev server; the built bundle is served by FastAPI.

## Work Guidance

- Keep components typed and free of `any` except where the force-graph library forces it (`GraphView`).
- Preserve the no-API-key banner and offline/reconnecting states — the app must be usable statistical-only.
- When the backend adds/renames stats keys, update `parseStageStats` + `stageTimings` here.
- Keep isolated graph nodes visible when filtering edges so singleton communities remain represented and color-coded; the core-network view may scope them out of the initial canvas without removing them from graph data.
- Seed each displayed force graph independently and keep the canvas fitted to its actual container; small components use a bounded zoom so a two-node relationship remains readable.

## Verification

- `cd frontend && npm run build` — must pass (tsc + vite).
- Manual E2E: upload a doc, open the graph, exercise search / filters / path query / exports.

## Child DOX Index

- [`src/components/AGENTS.md`](src/components/AGENTS.md) — UI components
- Frontend-owned: `src/App.tsx`, `src/api.ts`, `src/types.ts`, `src/graphUtils.ts`, `src/colors.ts`, `src/styles.css`, `src/main.tsx`, build/config files
