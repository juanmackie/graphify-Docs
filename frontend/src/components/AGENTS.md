# Frontend Components AGENTS.md

## Purpose

React UI components for the document list and graph exploration experience.

## Ownership

- `DocumentList.tsx` — registry rows: status, progress, RE-RUN, OPEN GRAPH, stage-timing breakdown
- `GraphView.tsx` — `react-force-graph-2d` wrapper: community colors, size by degree, search/path/filter, node panel, toolbar stats chip
- `UploadPage.tsx` — drag-and-drop upload + live job progress
- `NodePanel.tsx` — clicked-node details (snippet, neighbors)
- `SearchBar.tsx`, `FilterBar.tsx`, `Legend.tsx`, `PathQuery.tsx`, `ExportBar.tsx` — supporting controls

## Local Contracts

- **`DocumentList.tsx`**: for `done` rows, parse `doc.stats_json` and render the stage breakdown (`parse 2.6s · llm 3m 12s · total 3m 20s · 142 chunks · 50 LLM-selected · concurrency 4`) via `graphUtils` helpers. Old docs with `stats_json = null`, error rows, and in-flight rows render no breakdown.
- **`GraphView.tsx`**: toolbar `stat-chip` shows visible/total concept and link counts plus the same stage breakdown from `graph.document.stats`. The reading guide explains extracted assertions versus inferred associations; the map view offers a readable core network, selected-component focus, and all-visible scope. Selecting a node focuses its neighborhood while keeping unrelated nodes and links moderately visible for navigation, labels are progressively disclosed, and directed links show arrows. Force-graph node/link painting is fully custom (`nodeCanvasObject` / `linkCanvasObject`) with seeded positions, community layout force, curved parallel links, and bounded small-component zoom. Isolated nodes remain visible during edge filtering so singleton community colors are not hidden.
- **`FilterBar.tsx` / `NodePanel.tsx`**: provenance and assertion/association filters plus evidence-rich neighbor inspection. Inferred-support thresholds apply to associations while typed assertions remain visible; node focus presents the strongest connections first. These remain read-only until the deferred correction-editor milestone. Search and path tracing reveal a hidden peripheral component before centering it.
- **`PathQuery.tsx`**: BFS shortest path computed client-side on `graph.links` (see `graphUtils.shortestPathIds`).
- All components are presentational — data comes from `api.ts`; no direct fetch in components.

## Work Guidance

- Keep the document list compact: one timing line, mono font, muted color, no layout shift when it appears.
- Preserve empty/error/no-key states — the app must never show a bare spinner.
- When adding a component, add it to this index and keep `ExportBar` in the toolbar.

## Verification

- `cd frontend && npm run build` — type-checks all components.
- Render smoke test (throwaway): `react-dom/server` + esbuild against `DocumentList` with representative records (done-with-stats, done-null, error, in-flight).

## Child DOX Index

- No child AGENTS.md files.
