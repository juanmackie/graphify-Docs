# graphify Docs agent contract

## Operating Standard

- Apply `C:\Users\juanm\Documents\GitHub\Vibe Coding Rules 10.md` (V10) as the repository operating standard; read it in full before substantive work.
- This file is the nearest-owning contract. It refines the parent policy with repository-specific facts and cannot weaken a mandatory parent rule; conflicts resolve to the parent.

## Scope and Ownership

- `backend/` — FastAPI app (`app/`: `ingestion/`, `extraction/`, `graph/`, `export/`, `pipeline.py`, `jobs.py`, `store.py`, `config.py`), `tests/`, `benchmarks/`, `data/` (SQLite `documents.db`, `uploads/`). Dependencies in `requirements.txt` (uv-managed venv at `backend/.venv`).
- `frontend/` — React 18 + TypeScript + Vite SPA (`docgraph-frontend`); force-graph visualization, upload, exports. No test runner configured.
- `docs/` — documentation assets: pipeline diagram, screenshots, `docs/verification/` manual e2e notes.
- `plans/` — working plan files for feature work (not project documentation).
- Root-owned files: `README.md`, `PLAN.md`, `.env`, `.env.example`, `.gitignore`, `run.ps1`, `run.sh`.
- `run.ps1` / `run.sh` — single-command local run: create venvs, install deps, build frontend, start uvicorn on `http://localhost:8000`.

## Constraints

- Local, single-user, no accounts: no authentication or database servers, ever. SQLite file storage only. CORS is restricted to local frontend origins — do not loosen it.
- Keep the LLM optional: the app must always run in statistical-only mode without an API key. LLM extraction targets any OpenAI-compatible endpoint; malformed LLM JSON is repaired, not trusted.
- Delete duplication, not capability: strip duplicated logic, redundant abstractions, and overlapping responsibilities, but a part that does a real job stays. Prefer standard/existing libraries over custom solutions.
- Optimizations must be evidence-based: measure stage timings before and after (see `backend/benchmarks/` and `plans/stage-timings.md`).
- Public-repository hygiene: never track `.env`, `.pi/`, `.pi-subagents/`, `PLAN.md`, local settings, or generated build artifacts (`frontend/dist/`, caches). Review tracked files before publishing.
- Graph construction depends on pinned `networkx>=3.0,<3.5` and `python-louvain==0.16`; keep them compatible when touching `backend/app/graph/`.
- Preserve data invariants of `backend/data/documents.db` and uploaded files; uploads and parsed documents are user data.

## Verification

- Backend tests: `cd backend && .venv/Scripts/python.exe -m pytest` (or `.venv/bin/python -m pytest`); `pytest` and `httpx` are declared in `backend/requirements.txt` and `backend/tests/` holds the suite (`test_api.py`, `test_graph.py`, `test_export.py`, `test_parser.py`, and others).
- Frontend build (includes type check): `cd frontend && npm run build` (`tsc && vite build` per `frontend/package.json`). There is no frontend test runner; exercising the UI in a browser is the check.
- Manual end-to-end: run `./run.sh` or `powershell ./run.ps1`, upload a document, exercise graph/explore/export flows; see `docs/verification/manual-e2e-2026-09-01.md` for the recorded procedure. A successful build is not evidence of visual or interaction correctness.
- Benchmarks (when optimizing): `backend/benchmarks/extraction_speed.py`, `backend/benchmarks/microbatch_eval.py` — measure before and after.

## Child contracts

Child AGENTS.md files refine this file under V10 section 1 and cannot weaken the parent policy:

- `backend/AGENTS.md`
- `backend/tests/AGENTS.md`
- `backend/app/ingestion/AGENTS.md`
- `backend/app/extraction/AGENTS.md`
- `backend/app/graph/AGENTS.md`
- `backend/app/export/AGENTS.md`
- `frontend/AGENTS.md`
- `frontend/src/components/AGENTS.md`
- `docs/AGENTS.md`
- `plans/AGENTS.md`
