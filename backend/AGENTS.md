# Backend AGENTS.md

## Purpose

FastAPI backend for the document knowledge-graph tool: upload → parse → chunk →
LLM + statistical extraction → merge → graph build → exports. Single-user,
local-first; no DB servers, no auth.

## Ownership

- `app/main.py` — routes, static serving of the frontend build
- `app/pipeline.py` — end-to-end job pipeline and stage timing recording
- `app/config.py` — env-driven settings
- `app/store.py` — sqlite index + per-document files under `data/uploads/{doc_id}/`
- `app/jobs.py` — in-process background job threads
- `requirements.txt`, `benchmarks/` (extraction speed / micro-batch evals)

## Local Contracts

- **Env config**: read from `backend/.env` → repo-root `.env` → cwd `.env`, first match wins per key; real environment variables always override. See `README.md` for the full table (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `EXTRACTION_MODE`, `LLM_CONCURRENCY`, `LLM_TIMEOUT_SECONDS`, `LLM_CHUNK_FRACTION`, `MAX_GRAPH_NODES`, `MAX_GRAPH_EDGES`, `DATA_DIR`, …).
- **Data layout**: `DATA_DIR` (default `./data`) holds `documents.db` + `uploads/{doc_id}/` with `source.{ext}`, `text.txt`, `graph.json`, `meta.json`, `llm_checkpoint.json`.
- **Pipeline** (`pipeline.py`): parse → chunk → select → LLM extraction (skipped without a key) → statistical (always runs) → merge → graph build. Records per-stage seconds (`parsing_seconds`, `chunking_seconds`, `statistical_seconds`, `llm_seconds`, `pipeline_seconds` + LLM metrics) into `graph.document.stats` and `stats_json` on completion.
- **Jobs**: background threads, in-process. A server restart marks non-terminal docs `error` ("Interrupted by server restart"); recovery is `POST /api/documents/{id}/reprocess` from the saved source file (RE-RUN in the UI).
- **API surface**: `/api/health`, `/api/config`, `/api/documents` (list/upload/delete), `/api/documents/{id}/status|graph|reprocess`, `/api/documents/{id}/export/{html|report|csv}`. Production serves `frontend/dist` at `/`.
- **Browser boundary**: CORS permits only the Vite dev origins `http://localhost:5173` and `http://127.0.0.1:5173`; production uses same-origin requests.
- **Pinned deps**: `networkx>=3.0,<3.5` + `python-louvain==0.16` (compatibility); PDF parsing uses `pypdf`; LLM uses the `openai` SDK against any OpenAI-compatible endpoint.
- **Deliberately disabled**: micro-batching (combining chunks per LLM call) — attribution risk on malformed JSON; see `benchmarks/microbatch_eval.py` for the trade-off estimate.
- **Graph caps**: `MAX_GRAPH_NODES` (600) / `MAX_GRAPH_EDGES` (2500) keep large documents responsive.

## Work Guidance

- Keep the LLM optional: the app must always work in statistical-only mode (no API key, zero cost).
- Fail fast on hung upstreams: `LLM_TIMEOUT_SECONDS` bounds per-call time and a failed chunk is counted as `llm_error`, the job continues.
- Preserve stage timing stats — the frontend renders them (see `frontend/AGENTS.md`).
- Never change the pinned networkx/python-louvain versions without re-running the full suite.

## Verification

- `cd backend && uv run pytest -q` — 90 tests: parsing, chunking, extraction, merging, graph building, API, exports (LLM mocked, offline).
- Manual E2E: `uvicorn app.main:app` + `npm run dev` (frontend); upload a real PDF and confirm the graph renders.

## Child DOX Index

- [`app/ingestion/AGENTS.md`](app/ingestion/AGENTS.md) — parsers, chunker, LLM chunk selector
- [`app/extraction/AGENTS.md`](app/extraction/AGENTS.md) — LLM + statistical extraction, merge/dedup
- [`app/graph/AGENTS.md`](app/graph/AGENTS.md) — graph.json builder, community detection
- [`app/export/AGENTS.md`](app/export/AGENTS.md) — HTML / Markdown / CSV exports
- [`tests/AGENTS.md`](tests/AGENTS.md) — pytest verification suite
- Backend-owned: `app/main.py`, `app/config.py`, `app/store.py`, `app/jobs.py`, `app/pipeline.py`, `requirements.txt`, `benchmarks/`
