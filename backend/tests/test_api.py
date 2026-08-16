"""Integration tests for the FastAPI endpoints (upload → job → status → graph)."""
from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _wait_done(doc_id: str, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        rec = client.get(f"/api/documents/{doc_id}/status").json()
        if rec["status"] in ("done", "error"):
            return rec
        time.sleep(0.1)
    raise AssertionError("timed out waiting for processing")


def test_health():
    assert client.get("/api/health").json() == {"ok": True}


def test_config():
    cfg = client.get("/api/config").json()
    assert "has_api_key" in cfg
    assert "model" in cfg


def test_upload_unsupported_extension():
    res = client.post(
        "/api/documents",
        files={"file": ("notes.xyz", b"hello", "application/octet-stream")},
    )
    assert res.status_code == 400
    assert "Unsupported file type" in res.json()["detail"]


def test_upload_empty_file():
    res = client.post(
        "/api/documents",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert res.status_code == 400


def test_upload_legacy_doc_rejected():
    res = client.post(
        "/api/documents",
        files={"file": ("old.doc", b"\xd0\xcf\x11\xe0 binary", "application/msword")},
    )
    assert res.status_code == 400
    assert "docx" in res.json()["detail"]


def test_end_to_end_txt(sample_txt: Path):
    res = client.post(
        "/api/documents",
        files={"file": ("sample.txt", sample_txt.read_bytes(), "text/plain")},
    )
    assert res.status_code == 200
    doc_id = res.json()["doc_id"]

    rec = _wait_done(doc_id)
    assert rec["status"] == "done", rec.get("error")
    assert rec["node_count"] > 0

    graph = client.get(f"/api/documents/{doc_id}/graph").json()
    assert graph["document"]["id"] == doc_id
    assert len(graph["nodes"]) == rec["node_count"]
    assert len(graph["nodes"]) >= 5
    assert graph["document"]["stats"]["chunks"] >= 1
    assert graph["document"]["schema_version"] == 2
    assert graph["document"]["stats"]["graph_schema_version"] == 2
    if graph["links"]:
        assert {"relation_key", "direction", "kind", "provenance", "evidence", "quality"} <= set(graph["links"][0])
    # graph references are internally consistent
    node_ids = {n["id"] for n in graph["nodes"]}
    for link in graph["links"]:
        assert link["source"] in node_ids
        assert link["target"] in node_ids

    # list contains it
    docs = client.get("/api/documents").json()
    assert any(d["id"] == doc_id for d in docs)


def test_end_to_end_pdf(sample_pdf: Path):
    res = client.post(
        "/api/documents",
        files={"file": ("sample.pdf", sample_pdf.read_bytes(), "application/pdf")},
    )
    assert res.status_code == 200
    doc_id = res.json()["doc_id"]
    rec = _wait_done(doc_id)
    assert rec["status"] == "done", rec.get("error")


def test_graph_missing_document_404():
    assert client.get("/api/documents/nope/graph").status_code == 404
    assert client.get("/api/documents/nope/status").status_code == 404


def test_delete_document(sample_txt: Path):
    res = client.post(
        "/api/documents",
        files={"file": ("todel.txt", sample_txt.read_bytes(), "text/plain")},
    )
    doc_id = res.json()["doc_id"]
    _wait_done(doc_id)
    assert client.delete(f"/api/documents/{doc_id}").status_code == 200
    assert client.get(f"/api/documents/{doc_id}/status").status_code == 404


# ── job recovery: stale marking + reprocess ───────────────────────────
def _mark_interrupted(doc_id: str) -> None:
    from app.store import store

    store.set_status(doc_id, "extracting", progress=0.5)


def test_stale_jobs_marked_on_startup():
    from app.store import store

    doc_id = store.create_document("stuck.txt", ".txt", 42)
    _mark_interrupted(doc_id)
    # Startup lifespan must flag the mid-flight doc as failed (threads never
    # survive a restart), so the UI can offer RE-RUN instead of an eternal
    # spinner.
    with TestClient(app) as c:
        rec = c.get(f"/api/documents/{doc_id}/status").json()
    assert rec["status"] == "error"
    assert "Interrupted" in (rec["error"] or "")


def test_reprocess_reruns_failed_document(sample_txt: Path):
    res = client.post(
        "/api/documents",
        files={"file": ("rerun.txt", sample_txt.read_bytes(), "text/plain")},
    )
    doc_id = res.json()["doc_id"]
    _wait_done(doc_id)

    # Simulate a job that died mid-extraction (e.g. server restart).
    _mark_interrupted(doc_id)
    assert client.get(f"/api/documents/{doc_id}/status").json()["status"] == "extracting"

    res = client.post(f"/api/documents/{doc_id}/reprocess")
    assert res.status_code == 200
    assert res.json()["status"] == "queued"

    rec = _wait_done(doc_id)
    assert rec["status"] == "done", rec.get("error")
    assert rec["node_count"] > 0


def test_reprocess_missing_document_404():
    assert client.post("/api/documents/nope/reprocess").status_code == 404


def test_reprocess_missing_source_409():
    from app.store import store

    # Record exists in the index but its source file was never saved.
    doc_id = store.create_document("ghost.txt", ".txt", 10)
    res = client.post(f"/api/documents/{doc_id}/reprocess")
    assert res.status_code == 409
    assert "upload" in res.json()["detail"]


def test_reprocess_rejects_while_running():
    import threading
    import time

    from app.jobs import jobs
    from app.store import store

    doc_id = store.create_document("busy.txt", ".txt", 10)
    store.save_source(doc_id, b"hello world", ".txt")
    # Deterministically simulate an in-flight job: register a live thread.
    blocker = threading.Thread(target=lambda: time.sleep(2), daemon=True)
    blocker.start()
    with jobs._lock:
        jobs._threads[doc_id] = blocker
    try:
        res = client.post(f"/api/documents/{doc_id}/reprocess")
        assert res.status_code == 409
        assert "running" in res.json()["detail"]
    finally:
        with jobs._lock:
            jobs._threads.pop(doc_id, None)
        blocker.join(timeout=3)
