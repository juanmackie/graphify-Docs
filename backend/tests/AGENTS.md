# Tests AGENTS.md

## Purpose

Pytest verification for the backend. 90 tests covering parsing, chunking, extraction (mocked LLM), merging, graph building, API, and exports.

## Ownership

- `conftest.py` — shared fixtures and environment isolation
- `test_parser.py`, `test_chunker.py`, `test_selector.py`, `test_llm.py`, `test_statistical.py`, `test_merge.py`, `test_graph.py`, `test_export.py`, `test_api.py`

## Local Contracts

- **`conftest.py`** sets `DATA_DIR` to a temp dir and pins `OPENAI_API_KEY=""`, `OPENAI_BASE_URL=http://localhost:9/v1`, `OPENAI_MODEL=test-model` **before any `app.*` import** (settings are read at import time). Real env vars win over `.env` files, so a developer's local `.env` must never trigger real API calls in tests.
- Tests stay offline and deterministic: no network, no real LLM, no shared state.
- Fixtures include a small sample document in every supported format.

## Work Guidance

- Add a test for every new backend behavior; bug fixes get a regression test first.
- Never relax the conftest isolation to make a test pass.
- Full suite must be green before a DOX closeout: `cd backend && uv run pytest -q`.
- API boundary tests must keep local-dev CORS allowlisted and reject unrelated origins.

## Verification

- `cd backend && uv run pytest -q` — all pass, no failures.
- Optional: `python -m pytest -q` if using the repo venv directly.

## Child DOX Index

- No child AGENTS.md files.
