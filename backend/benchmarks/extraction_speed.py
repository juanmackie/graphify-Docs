"""Local deterministic benchmark for extraction scheduling.

Uses an in-memory mock provider, so it measures client scheduling overhead and
concurrency behavior rather than real provider latency.
"""
from __future__ import annotations

import json
import time
from types import SimpleNamespace

import httpx

from app.extraction import llm
from app.ingestion.selector import select_chunks


def response() -> dict:
    return {
        "choices": [{"message": {"content": '{"entities": [], "relations": []}'}}]
    }


def run(chunks: list[str], concurrency: int) -> tuple[float, dict]:
    def handler(request: httpx.Request) -> httpx.Response:
        time.sleep(0.02)
        return httpx.Response(200, json=response())

    client = llm._make_client(http_client=httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://benchmark"
    ))
    original = llm._make_client
    llm._make_client = lambda http_client=None: client
    try:
        started = time.perf_counter()
        result = llm.extract_document(chunks, concurrency=concurrency)
        return time.perf_counter() - started, result
    finally:
        llm._make_client = original


def main() -> None:
    llm.settings = SimpleNamespace(
        has_api_key=True,
        openai_api_key="benchmark",
        openai_model="benchmark",
        openai_base_url="http://benchmark",
        llm_timeout_seconds=30.0,
        llm_max_retries=0,
        llm_concurrency=4,
    )
    chunks = [f"# Section {i}\n\nunique term {i}" for i in range(40)]
    selected = select_chunks(chunks, mode="balanced", fraction=0.35, minimum=1, maximum=250)
    for label, workload in (("full", chunks), ("balanced", selected.chunks)):
        for concurrency in (1, 4):
            seconds, result = run(workload, concurrency)
            print(
                f"{label:8} chunks={len(workload):2} concurrency={concurrency} "
                f"elapsed={seconds:.3f}s max_active={result['llm_max_active']}"
            )


if __name__ == "__main__":
    main()
