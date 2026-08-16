# Extraction AGENTS.md

## Purpose

Hybrid entity/relationship extraction: LLM (OpenAI-compatible, optional) + statistical keyword/co-occurrence pass, merged and deduplicated.

## Ownership

- `llm.py` — per-chunk structured JSON extraction with concurrency + caching
- `statistical.py` — YAKE keywords + chunk co-occurrence edges
- `merge.py` — name normalization, entity/edge dedup and merging

## Local Contracts

- **`llm.py`**: one system prompt demanding exact JSON (`response_format=json_object`, retried without it if the server rejects). Relations include directed/undirected semantics, assertion/association kind, original label, and verbatim evidence when available; legacy mocked responses default safely to directed assertions with snippet evidence. Robust parsing uses repairs (the `json-repair` library, plus fence/brace extraction). `AdaptiveRateLimiter` starts at `LLM_CONCURRENCY`, halves capacity on 429/5xx, recovers one slot at a time. Per-chunk checkpoint cache (`llm_checkpoint.json`, keyed by versioned prompt+chunk hash) makes re-runs instant. No-key mode returns `{"llm_used": False, …}` immediately.
- **`statistical.py`**: always runs, zero cost — YAKE keyword ranking plus deterministic line-aware sentence/paragraph/window candidate linking. PDF line breaks are locality boundaries so table headers do not create page-wide cliques; noisy fragments are rejected, window-only support is bounded for long documents, and inferred degree is capped. Candidates validate that both endpoints occur in the document and emit explicit undirected `association` edges with repeat/locality support and evidence; the legacy chunk-local helper remains compatible.
- **`merge.py`**: canonical entity key = lowercase + whitespace collapse + leading-article strip; equivalent relation labels share a stable `relation_key` (inverse aliases preserve direction), missing relation endpoints are materialized as minimal concept nodes, and edges merge evidence/provenance plus deterministic quality/confidence. Self-loops and malformed relations remain guarded.
- **LLM metrics** fed back to the pipeline: `llm_seconds`, `llm_avg_chunk_seconds`, `llm_max_chunk_seconds`, `llm_concurrency`, `llm_throttle_events`, `llm_cache_hits`/`misses`, `llm_errors`.

## Work Guidance

- Keep statistical associations sparse and explainable: prefer typed LLM assertions when available, and never reintroduce page-wide co-occurrence windows for PDF table text.
- Keep micro-batching **off** (attribution risk on malformed JSON); evaluate with `benchmarks/microbatch_eval.py` if revisited.
- A failed chunk must degrade gracefully: counted as `llm_error`, the job continues with the rest.
- Edge `tag` must stay `llm` | `cooccurrence` — the UI and CSV export depend on it.

## Verification

- `pytest tests/test_llm.py tests/test_statistical.py tests/test_merge.py`
- `test_llm.py` uses a mocked HTTP transport with canned JSON; tests must never hit a real provider (conftest pins `OPENAI_API_KEY=""`).

## Child DOX Index

- No child AGENTS.md files.
