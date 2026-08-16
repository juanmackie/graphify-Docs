# Knowledge Graph Connection Quality Plan

## Context

DocGraph already has a local FastAPI + React pipeline with optional LLM extraction, statistical co-occurrence edges, community detection, force-directed visualization, search/filter/path exploration, and exports. The requested direction is to take the strongest behaviors from Neo4j Labs' LLM Graph Builder, AI Knowledge Graph, Knowledge-Graph-Builder, CleanGraph, and skglab/PyVis—especially better node connections—without replacing the local-first architecture.

Confirmed first milestone: **quality foundation only**. Prioritize missing links and relation quality; defer the persistent editor/review CRUD to a later milestone, while making the graph schema and provenance model compatible with saved correction overlays. Future user-created/edited relations should support controlled common labels plus custom labels, and rejected edges should be hidden through an overlay rather than deleted from raw extraction.

Current constraints discovered in the code:

- `backend/app/extraction/llm.py` extracts relations independently per selected chunk; it does not perform document-level entity resolution or cross-chunk relation completion.
- `backend/app/extraction/statistical.py` only creates generic `co-occurs with` edges from paragraph-local YAKE keywords.
- `backend/app/extraction/merge.py` normalizes names and relation strings but does not validate endpoints against their source text, normalize relation vocabulary, score confidence, or retain multiple evidence items.
- `merge_all` drops dangling relations when an LLM emits a valid relation endpoint that was not also listed in its entity array; this is a direct source of missing connections.
- `backend/app/graph/builder.py` emits stable IDs and provenance tags but only exposes one tag, one snippet, weight, and degree/community values.
- `store.py` already persists raw extraction metadata and `graph.json` per document, so future corrections can be layered on local files without adding a database server.
- The React graph surface already has custom force-graph painting, filters, path tracing, node details, and exports, but neighbor rows omit edge weight, provenance, confidence, and evidence.
- The frontend has no test runner; backend pytest and the frontend TypeScript build are the established gates.

## Approach

Keep the current force-graph dependency, SQLite/filesystem storage, optional LLM behavior, and stable IDs. Do not introduce Neo4j, Bloom, Cytoscape, PyVis, accounts, or a server database just to copy their heavier deployment stacks. Borrow their useful behaviors: schema-aware extraction and explanation, interactive graph review, explicit extracted-vs-inferred provenance, and a future human-in-the-loop correction model.

1. **Improve relation capture and endpoint survival.** Make the extraction contract explicitly distinguish directed typed assertions from undirected inferred associations. Preserve LLM relation endpoints even when the model omitted them from `entities`, materializing a minimal endpoint node from the relation context instead of dropping the edge. Track source chunk/paragraph identifiers wherever available.
2. **Improve relation quality.** Normalize common equivalent labels into stable canonical relation keys, preserve the original model label, validate self-loops/empty/unknown relations, retain direction for LLM assertions, and add deterministic quality/confidence signals based on evidence, repetition, source type, and endpoint support. Do not pretend co-occurrence is a directed semantic assertion.
3. **Recover missing links without making LLM mandatory.** Use the complete document for statistical candidate generation, with sentence/paragraph/window locality and repeat-support scoring so recurring entities can connect across selected LLM chunk boundaries. When an LLM is available, add a bounded document-aware completion/validation step only where the existing extracted entities and evidence produce plausible candidates; statistical-only mode must remain useful and deterministic.
4. **Expose explainability in the graph and current UI.** Extend `graph.json` links with backward-compatible provenance, direction/association semantics, quality/confidence, original relation, and evidence references/snippets. Update filters, tooltips, and the node panel so users can see why an edge exists and distinguish extracted, inferred, mixed, and weak links before the later editor milestone.
5. **Prepare for future saved corrections without implementing CRUD now.** Version the graph/refinement fields and keep raw extraction separate from the effective graph contract. The later editor can hide rejected edges and add approved/custom relations as an overlay, resettable without reprocessing.
6. **Keep exports honest.** Export the effective quality-scored graph with provenance/evidence fields and a method note; preserve existing HTML/Markdown/CSV routes and compatibility.

## Files to modify

- `backend/app/extraction/llm.py` — extraction prompt/parser fields for relation direction, canonical/original labels, and evidence/chunk metadata.
- `backend/app/extraction/statistical.py` — sentence/paragraph/window candidate generation, repeat/locality scoring, and explicit undirected association semantics.
- `backend/app/extraction/merge.py` — endpoint materialization, relation canonicalization/validation, provenance/evidence merging, and confidence calculation.
- `backend/app/graph/builder.py` — versioned backward-compatible node/link schema, quality fields, stable IDs, and graph stats.
- `backend/app/pipeline.py` — pass full-document context and extraction metadata through the revised merge/build stages.
- `backend/tests/test_llm.py`, `test_statistical.py`, `test_merge.py`, `test_graph.py`, `test_api.py` — regression coverage for missing endpoints, cross-context candidates, directed vs inferred edges, scoring, schema compatibility, and no-key mode.
- `frontend/src/types.ts`, `api.ts`, `graphUtils.ts` — new typed link/provenance/quality fields and filters/helpers.
- `frontend/src/components/GraphView.tsx`, `NodePanel.tsx`, `FilterBar.tsx`, and possibly a small evidence/quality component; `frontend/src/styles.css` — explainable edge rendering and review-oriented inspection, without edit controls yet.
- `backend/app/export/html.py`, `report.py`, `csv.py` — display/export quality, direction, provenance, original label, and evidence metadata.
- `README.md` and applicable `AGENTS.md` files — document the revised graph contract and the deferred correction-editor milestone.

## Reuse

- Existing bounded-concurrent, checkpointed LLM calls and robust JSON repair in `backend/app/extraction/llm.py`; preserve retries, timing metrics, and no-key mode.
- Existing YAKE extraction and paragraph locality in `backend/app/extraction/statistical.py` as the base for stronger deterministic candidate scoring.
- Existing canonical merge and stable `node_id`/`edge_id` logic in `merge.py` and `graph/builder.py`.
- Existing `meta.json`, `graph.json`, per-document directory, and export endpoints; avoid duplicate storage systems.
- Existing force-directed graph, custom canvas painting, filter/path utilities, node panel, and export bar in the frontend.
- Referenced-tool takeaways: Bloom-like exploration, KGB-style extracted/inferred origin tracking, CleanGraph-style explainability and future correction overlays, and PyVis-like portable interactive output are behaviors to adopt—not dependencies to add.

## Steps

- [x] Freeze a versioned, backward-compatible relation/evidence/quality schema.
- [x] Extend LLM extraction parsing/prompting with relation semantics and source evidence while preserving old mocked responses.
- [x] Add deterministic full-document candidate linking with sentence/paragraph/window locality, repetition support, endpoint validation, and undirected association tagging.
- [x] Update merge logic to canonicalize equivalent relation labels, retain missing relation endpoints, merge evidence/provenance, and calculate quality/confidence.
- [x] Update graph assembly/stats and pipeline wiring; preserve graph caps, stable IDs, communities, and stage timings.
- [x] Add frontend inspection/filtering for provenance, direction/association, confidence/quality, and evidence; keep the current no-key UX.
- [x] Update HTML/report/CSV exports and documentation for the new fields and future correction-overlay contract.
- [x] Add regression tests and run the complete backend suite plus frontend build.

## Verification

- `cd backend && uv run pytest -q`: no network calls; prove relations survive omitted entity arrays, cross-paragraph/cross-chunk candidates are deterministic, relation direction is preserved, inferred edges remain undirected/marked, quality fields merge correctly, old graph inputs remain readable, and statistical-only processing still completes.
- `cd frontend && npm run build`: TypeScript and Vite build pass with the revised graph types/components.
- Manual E2E with and without `OPENAI_API_KEY`: upload a representative document, inspect cross-boundary links, relation labels/direction, provenance/evidence/quality filters, path tracing, communities, isolated nodes, and HTML/Markdown/CSV exports.
- Confirm graph caps, stable IDs, existing stage timing displays, checkpoint/retry behavior, and no-API-key banner remain intact.

## Deferred next milestone

Add the CleanGraph-style persistent editor: approve/reject/edit/add/merge operations stored as a correction overlay, with controlled common labels plus custom labels, reset/reprocess behavior, and effective-graph exports. Rejected raw edges should remain auditable but be hidden from the normal effective graph.
