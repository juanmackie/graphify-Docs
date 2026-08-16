"""End-to-end document processing pipeline.

Stages: parse → chunk → LLM + statistical extraction → merge → graph build.
Runs in a background thread (see jobs.py); progress is persisted to the store.
"""
from __future__ import annotations

import json
import time

from .config import settings
from .extraction import llm, merge, statistical
from .graph.builder import build_graph
from .ingestion.chunker import chunk_text
from .ingestion.parser import parse_document
from .ingestion.selector import select_chunks
from .store import store


def process_document(doc_id: str) -> None:
    pipeline_started = time.perf_counter()
    record = store.get(doc_id)
    if record is None:
        return
    ext = record["ext"]
    source_path = store.source_path(doc_id, ext)

    # 1. Parse ────────────────────────────────────────────────────────
    stage_started = time.perf_counter()
    store.set_status(doc_id, "parsing", 0.05)
    parsed = parse_document(source_path)
    store.save_text(doc_id, parsed.text)
    parsing_seconds = time.perf_counter() - stage_started

    # 2. Chunk ────────────────────────────────────────────────────────
    stage_started = time.perf_counter()
    store.set_status(doc_id, "chunking", 0.15)
    chunks = chunk_text(
        parsed.text,
        max_chars=settings.chunk_chars,
        overlap_chars=settings.chunk_overlap,
    )
    chunking_seconds = time.perf_counter() - stage_started
    if not chunks:
        store.set_status(doc_id, "error", error="No text to analyze.")
        return

    extraction_mode = record.get("extraction_mode") or settings.extraction_mode
    selection = select_chunks(
        chunks,
        mode=extraction_mode,
        fraction=settings.llm_chunk_fraction,
        minimum=settings.llm_min_chunks,
        maximum=settings.llm_max_chunks,
    )

    # 3. LLM extraction (skipped without an API key) ──────────────────
    store.set_status(doc_id, "extracting", 0.2)
    llm_result = llm.extract_document(
        selection.chunks,
        progress_cb=lambda p: store.update(doc_id, progress=0.2 + p * 0.5),
        chunk_indices=selection.indices,
        concurrency=settings.llm_concurrency,
        checkpoint_path=store.doc_dir(doc_id) / "llm_checkpoint.json",
        progress_detail_cb=lambda detail: store.update(
            doc_id, progress_detail=json.dumps(detail)
        ),
    )

    # 4. Statistical extraction (always runs — zero cost) ─────────────
    stage_started = time.perf_counter()
    stats = statistical.extract_statistical(
        chunks,
        parsed.text,
        entity_names=llm_result["entities"],
    )
    statistical_seconds = time.perf_counter() - stage_started
    keyword_dicts = stats["keywords"]
    cooc_edges = stats["edges"]

    # 5. Merge + dedup ────────────────────────────────────────────────
    merged = merge.merge_all(
        llm_entities=llm_result["entities"],
        llm_relations=llm_result["relations"],
        keywords=keyword_dicts,
        cooccurrence_edges=cooc_edges,
    )

    # 6. Graph build + community detection ────────────────────────────
    store.set_status(doc_id, "clustering", 0.85)
    graph = build_graph(
        doc_id=doc_id,
        doc_name=record["name"],
        entities=merged["entities"],
        edges=merged["edges"],
        stats={
            "chunks": len(chunks),
            "llm_selected_chunks": len(selection.chunks),
            "llm_selection_mode": selection.mode,
            "llm_edges": len(llm_result["relations"]),
            "cooc_edges": len(cooc_edges),
            "llm_errors": llm_result.get("llm_errors", 0),
            "llm_chunks": llm_result.get("llm_chunks", 0),
            "llm_seconds": llm_result.get("llm_seconds", 0.0),
            "llm_avg_chunk_seconds": llm_result.get("llm_avg_chunk_seconds", 0.0),
            "llm_max_chunk_seconds": llm_result.get("llm_max_chunk_seconds", 0.0),
            "llm_concurrency": llm_result.get("llm_concurrency", 1),
            "llm_max_active": llm_result.get("llm_max_active", 1),
            "llm_effective_concurrency": llm_result.get("llm_effective_concurrency", 1),
            "llm_throttle_events": llm_result.get("llm_throttle_events", 0),
            "llm_cache_hits": llm_result.get("llm_cache_hits", 0),
            "llm_cache_misses": llm_result.get("llm_cache_misses", 0),
            "llm_selection_fraction": round(len(selection.chunks) / len(chunks), 4),
            "parsing_seconds": round(parsing_seconds, 3),
            "chunking_seconds": round(chunking_seconds, 3),
            "statistical_seconds": round(statistical_seconds, 3),
        },
        llm_enabled=llm_result.get("llm_used", False),
        max_nodes=settings.max_nodes,
        max_edges=settings.max_edges,
        created_at=record["created_at"],
    )

    graph["document"]["stats"]["pipeline_seconds"] = round(time.perf_counter() - pipeline_started, 3)
    store.save_graph(doc_id, graph)
    # Guard: the document may have been deleted while the job was running.
    if store.get(doc_id) is None:
        return
    store.save_meta(
        doc_id,
        {
            "chunks": chunks,
            "keywords": keyword_dicts,
            "llm_entities": llm_result["entities"],
            "llm_relations": llm_result["relations"],
        },
    )
    store.update(
        doc_id,
        status="done",
        progress=1.0,
        error=None,
        node_count=graph["document"]["stats"]["nodes"],
        edge_count=graph["document"]["stats"]["edges"],
        stats_json=json.dumps(graph["document"]["stats"]),
    )
