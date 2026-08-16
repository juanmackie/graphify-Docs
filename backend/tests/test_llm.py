"""Tests for extraction.llm — parsing + OpenAI-compatible client (no network)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from app.extraction import llm

VALID_RESPONSE = {
    "entities": [
        {"name": "Knowledge Graph", "type": "concept", "snippet": "A knowledge graph represents entities."},
        {"name": "Neo4j", "type": "technology", "snippet": "Graph databases such as Neo4j store knowledge graphs."},
    ],
    "relations": [
        {"source": "Neo4j", "target": "Knowledge Graph", "relation": "stores", "snippet": "Neo4j stores knowledge graphs."},
    ],
}


def chat_response(content: str) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    }


# ── parsing ───────────────────────────────────────────────────────────
def test_parse_valid_response():
    result = llm.parse_llm_response(json.dumps(VALID_RESPONSE))
    assert result is not None
    assert len(result["entities"]) == 2
    assert len(result["relations"]) == 1
    assert result["relations"][0]["relation"] == "stores"


def test_parse_legacy_relation_gets_safe_semantics_and_evidence():
    result = llm.parse_llm_response(json.dumps(VALID_RESPONSE))
    assert result is not None
    relation = result["relations"][0]
    assert relation["direction"] == "directed"
    assert relation["kind"] == "assertion"
    assert relation["original_relation"] == "stores"
    assert relation["evidence"] == [{"text": "Neo4j stores knowledge graphs."}]


def test_parse_relation_semantics_and_evidence_metadata():
    content = json.dumps(
        {
            "entities": [{"name": "A"}, {"name": "B"}],
            "relations": [
                {
                    "source": "A",
                    "target": "B",
                    "relation": "Supports",
                    "direction": "undirected",
                    "kind": "association",
                    "snippet": "A and B are related.",
                    "evidence": [
                        {"text": "A and B are related.", "paragraph_index": 2, "sentence_index": 1}
                    ],
                }
            ],
        }
    )
    result = llm.parse_llm_response(content)
    assert result is not None
    relation = result["relations"][0]
    assert relation["relation"] == "supports"
    assert relation["original_relation"] == "Supports"
    assert relation["direction"] == "undirected"
    assert relation["kind"] == "association"
    assert relation["evidence"][0]["paragraph_index"] == 2
    assert relation["evidence"][0]["sentence_index"] == 1


def test_parse_inside_code_fence():
    content = f"Here you go:\n```json\n{json.dumps(VALID_RESPONSE)}\n```\nHope that helps."
    result = llm.parse_llm_response(content)
    assert result is not None
    assert len(result["entities"]) == 2


def test_parse_with_repairs():
    messy = (
        '{"entities": [{"name": "A", "type": "concept", "snippet": "x",},], '
        '"relations": [{"source": "A", "target": "B", "relation": "links",},],}'
    )
    result = llm.parse_llm_response(messy)
    assert result is not None
    assert result["entities"][0]["name"] == "A"


def test_parse_invalid_returns_none():
    assert llm.parse_llm_response("I have no idea") is None
    assert llm.parse_llm_response("") is None
    assert llm.parse_llm_response("[]") is None


def test_parse_drops_malformed_entries():
    content = json.dumps(
        {
            "entities": [{"name": "Good"}, {"name": ""}, {"type": "concept"}],
            "relations": [
                {"source": "A", "target": "B", "relation": "r"},
                {"source": "A", "target": "A", "relation": "self"},
                {"source": "", "target": "B", "relation": "bad"},
            ],
        }
    )
    result = llm.parse_llm_response(content)
    assert result is not None
    assert [e["name"] for e in result["entities"]] == ["Good"]
    assert len(result["relations"]) == 1


def test_parse_caps_and_lowercases_relation():
    many = [{"name": f"E{i}", "type": "concept"} for i in range(50)]
    content = json.dumps({"entities": many, "relations": []})
    result = llm.parse_llm_response(content)
    assert len(result["entities"]) == 30


# ── client behaviour (mocked transport) ───────────────────────────────
def _client_with_handler(handler):
    transport = httpx.MockTransport(handler)
    return llm._make_client(http_client=httpx.Client(transport=transport, base_url="http://test"))


def test_extract_chunk_ok():
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, json=chat_response(json.dumps(VALID_RESPONSE)))

    client = _client_with_handler(handler)
    result = llm.extract_chunk(client, "Some chunk text", 0)
    assert len(result["entities"]) == 2
    assert result["chunk"] == 0
    assert result["relations"][0]["chunk"] == 0
    assert result["relations"][0]["evidence"][0]["chunk_index"] == 0
    assert "error" not in result
    assert len(calls) == 1
    # json mode requested
    assert calls[0]["response_format"] == {"type": "json_object"}


def test_extract_chunk_retries_on_bad_json():
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            return httpx.Response(200, json=chat_response("Sorry, no JSON here."))
        return httpx.Response(200, json=chat_response(json.dumps(VALID_RESPONSE)))

    client = _client_with_handler(handler)
    result = llm.extract_chunk(client, "text", 2)
    assert len(result["entities"]) == 2
    assert len(calls) == 2


def test_extract_chunk_falls_back_without_json_mode():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("response_format"):
            return httpx.Response(400, json={"error": {"message": "response_format not supported"}})
        return httpx.Response(200, json=chat_response(json.dumps(VALID_RESPONSE)))

    client = _client_with_handler(handler)
    result = llm.extract_chunk(client, "text", 1)
    assert len(result["entities"]) == 2


def test_extract_document_without_key():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        llm,
        "settings",
        SimpleNamespace(has_api_key=False, openai_model="m", openai_base_url="u"),
    )
    try:
        result = llm.extract_document(["chunk1"])
        assert result["llm_used"] is False
        assert result["entities"] == []
    finally:
        monkeypatch.undo()


def test_extract_document_concurrency(monkeypatch):
    import threading
    import time

    monkeypatch.setattr(
        llm,
        "settings",
        SimpleNamespace(
            has_api_key=True,
            openai_api_key="test-key",
            openai_model="m",
            openai_base_url="http://test",
            llm_timeout_seconds=60.0,
            llm_max_retries=0,
            llm_concurrency=3,
        ),
    )
    active = 0
    max_active = 0
    lock = threading.Lock()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return httpx.Response(200, json=chat_response(json.dumps(VALID_RESPONSE)))

    client = _client_with_handler(handler)
    monkeypatch.setattr(llm, "_make_client", lambda http_client=None: client)
    result = llm.extract_document([f"c{i}" for i in range(6)], concurrency=3)
    assert result["llm_chunks"] == 6
    assert result["llm_max_active"] == 3
    assert result["llm_concurrency"] == 3


def test_extract_document_checkpoint_reuses_success(tmp_path, monkeypatch):
    monkeypatch.setattr(
        llm,
        "settings",
        SimpleNamespace(
            has_api_key=True,
            openai_api_key="test-key",
            openai_model="m",
            openai_base_url="http://test",
            llm_timeout_seconds=60.0,
            llm_max_retries=0,
            llm_concurrency=2,
        ),
    )
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=chat_response(json.dumps(VALID_RESPONSE)))

    checkpoint = tmp_path / "checkpoint.json"
    client = _client_with_handler(handler)
    monkeypatch.setattr(llm, "_make_client", lambda http_client=None: client)
    first = llm.extract_document(["same chunk"], chunk_indices=[4], checkpoint_path=checkpoint)
    second = llm.extract_document(["same chunk"], chunk_indices=[4], checkpoint_path=checkpoint)
    assert calls == 1
    assert first["llm_cache_misses"] == 1
    assert second["llm_cache_hits"] == 1
    assert len(second["entities"]) == 2


def test_extract_document_progress(monkeypatch):
    monkeypatch.setattr(
        llm,
        "settings",
        SimpleNamespace(
            has_api_key=True,
            openai_api_key="test-key",
            openai_model="m",
            openai_base_url="http://test",
            llm_timeout_seconds=60.0,
            llm_max_retries=1,
        ),
    )
    seen: list[float] = []
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(200, json=chat_response(json.dumps(VALID_RESPONSE)))

    client = _client_with_handler(handler)
    monkeypatch.setattr(llm, "_make_client", lambda http_client=None: client)
    result = llm.extract_document(["c1", "c2", "c3"], progress_cb=seen.append)
    assert result["llm_used"] is True
    assert len(result["entities"]) == 6  # 2 entities per chunk x 3 chunks
    assert seen == pytest.approx([1 / 3, 2 / 3, 1.0])
