# Ingestion AGENTS.md

## Purpose

Turn uploaded files into chunked plain text and pick which chunks the LLM sees.

## Ownership

- `parser.py` — per-format text extraction (PDF, DOCX, PPTX, TXT, MD, HTML)
- `chunker.py` — paragraph-aware overlapping chunking
- `selector.py` — adaptive, deterministic LLM chunk selection

## Local Contracts

- **`parser.py`**: supports `.pdf`, `.docx`, `.pptx`, `.txt`, `.md`, `.html`, `.htm`. Legacy `.doc` and encrypted PDFs raise clear errors. Returns `ParsedDocument(text, pages, format)`; empty pages (`extract_text() or ""`) are dropped. PDF text via `pypdf` per-page extraction.
- **`chunker.py`**: splits on blank-line paragraph boundaries, merges up to `max_chars` (default 4000 from `CHUNK_CHARS`), carries `overlap_chars` (default 200) of the previous chunk tail into the next; overlong paragraphs split sentence-aware via `_split_paragraph`.
- **`selector.py`**: modes `fast` (≤20% fraction) / `balanced` (default, 0.35 fraction) / `full` (all chunks); bounded by `LLM_MIN_CHUNKS` (12) / `LLM_MAX_CHUNKS` (250). Guarantees at least one chunk per coarse section, then fills remaining slots by distinctiveness/heading/length score — deterministic order.

## Work Guidance

- Keep extraction independent of format: parse → text → chunk is one pipeline; statistical extraction always sees the full text, selection only limits the LLM workload.
- Preserve the `ChunkSelection` shape (`chunks`, `indices`, `scores`, `total`, `mode`) — `pipeline.py` relies on `indices` matching chunks 1:1.
- Do not add format-specific logic in `chunker.py`; put it in `parser.py`.

## Verification

- `pytest tests/test_parser.py tests/test_chunker.py tests/test_selector.py`
- Fixtures: sample PDF/DOCX/TXT/PPTX/HTML files in `tests/conftest.py`; keep them small and committed.

## Child DOX Index

- No child AGENTS.md files.
