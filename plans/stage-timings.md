# Show pipeline stage timings in the UI

## Context

User reported a 2 MB PDF taking "a very long time." Diagnosis (measured on the
actual file, `AS 1851-2012`, 217 pages):

| Stage | Measured |
|---|---|
| PDF parse (pypdf 6.14.2) | **2.1 s** |
| Chunking (142 chunks @ 4000 chars) | instant |
| **LLM extraction (the real bottleneck)** | **minutes** — job was stuck at 29% in `extracting` |

The backend already records exact per-stage timings (`parsing_seconds`,
`chunking_seconds`, `statistical_seconds`, `llm_seconds`, `pipeline_seconds`,
plus LLM metrics) in two places:

1. `stats_json` column on the document row (returned by `GET /api/documents`
   and `/status` — the raw string is already in the JSON payload, the frontend
   just ignores it).
2. `graph.document.stats` in `graph.json` (returned by `GET /documents/{id}/graph`).

The frontend never displays them, so a slow stage is an opaque spinner and
users misattribute the delay to "parsing."

**Intended outcome:** finished documents show a small stage-timing breakdown
(parse · llm · total) in the document list and in the graph view, so it's
immediately visible where time went. Pure frontend change — no backend edits.

## Approach

Client-side only, mirroring the existing `progress_detail` pattern (raw JSON
string parsed in the component). Two surfaces:

1. **DocumentList rows** (`DocumentRecord.stats_json`) — for `done` docs, render
   a timing line under the meta: `parse 2.1s · llm 3m12s · total 3m20s`.
   When `llm_enabled` stats are present, also show the reason for slow runs:
   `142 chunks · 50 LLM-selected · concurrency 4`.
2. **GraphView toolbar** (`graph.document.stats`) — extend the existing
   `stat-chip` to include the same `parse · llm · total` breakdown.

Formatting: human durations (`2.1s`, `3m 12s`, `1h 02m`), only render fields
that exist, tolerate old documents with `stats_json = null` (show nothing, no
crash).

## Files to modify

- `frontend/src/types.ts` — add `stats_json?: string | null` to `DocumentRecord`
  (already in the API payload; just declare it).
- `frontend/src/graphUtils.ts` — add `formatDuration(seconds)` helper
  (e.g. `2.1s` / `3m 12s` / `1h 02m`) + a `parseStats(doc)` helper returning a
  typed breakdown object or null.
- `frontend/src/components/DocumentList.tsx` — for `done` rows, parse
  `doc.stats_json` and render the breakdown under `.doc-meta`.
- `frontend/src/components/GraphView.tsx` — extend the `stat-chip` line (or add
  a sibling span) using `graph.document.stats`.
- `frontend/src/styles.css` — small additions (muted mono timing text, maybe a
  `.stage-times` class); reuse existing `.doc-meta` / `.stat-chip` / `.muted`.

No backend changes: `store.list_documents()` already returns `stats_json`, and
`graph.document.stats` already carries every stage timing.

## Reuse

- `DocumentList.progressDetail()` — existing client-side JSON-string parsing
  pattern to copy for `stats_json`.
- `GraphView` `stat-chip` (line ~245 in GraphView.tsx) — where nodes/edges
  counts already render; extend in place.
- `.doc-meta`, `.muted`, `.stat-chip` CSS classes in `frontend/src/styles.css`.
- Stage keys already produced by `pipeline.py` → `build_graph(stats=...)` →
  `graph["document"]["stats"]` and `store.update(stats_json=...)`.

## Steps

- [ ] Add `stats_json?: string | null` to `DocumentRecord` in `types.ts`.
- [ ] Add `formatDuration` + `parseStageStats` helpers to `graphUtils.ts`
      (guarded: null/missing keys → null).
- [ ] In `DocumentList.tsx`: for `done` docs, parse `doc.stats_json` and render
      `parse X · llm Y · total Z` (+ chunk/LLM-count context when present)
      under the meta line; skip when absent.
- [ ] In `GraphView.tsx`: append the same breakdown to the existing `stat-chip`
      from `graph.document.stats` (fall back to current behavior when stats
      lack the timing keys).
- [ ] Add minimal CSS for the timing text (mono, muted, no layout shift).
- [ ] Verify with a real run (below); also confirm old docs without stats_json
      and error/queued rows are unaffected.

## Verification

1. `cd backend && uv run uvicorn app.main:app --port 8000` (or `./run.sh`),
   frontend via `npm run dev` in `frontend/`.
2. Upload the 2 MB `AS 1851-2012` PDF (or RE-RUN the existing stuck doc after
   restart — startup marks it `error`, making RE-RUN available). It uses the
   saved source file, so parsing runs again in ~2 s; the LLM stage will
   dominate and should now be *visible* in the list row while running the
   breakdown after `done`.
3. After `done`: confirm the DocumentList row shows e.g.
   `parse 2.1s · llm 3m12s · total 3m20s` (real numbers will differ), and the
   GraphView stat chip shows the same breakdown.
4. Upload a small TXT in no-key mode (statistical-only): timings show parse +
   total with no LLM line — confirms the LLM-only fields are omitted, not
   rendered as blank.
5. Visual check: an old doc from before this change (stats_json null) renders
   exactly as before.
