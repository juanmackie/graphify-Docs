"""Tests for the export modules + export API endpoints."""
from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.export.csv import render_csv_zip
from app.export.html import render_html_export
from app.export.report import render_markdown_report
from app.graph.builder import build_graph
from app.main import app

client = TestClient(app)

ENTITIES = [
    {"key": "attention", "name": "Attention", "type": "concept", "snippet": "Attention powers transformers.", "count": 4, "sources": ["llm"]},
    {"key": "transformers", "name": "Transformers", "type": "concept", "snippet": "", "count": 3, "sources": ["llm", "yake"]},
    {"key": "embedding", "name": "Embedding", "type": "concept", "snippet": "", "count": 2, "sources": ["yake"]},
]
EDGES = [
    {"source": "attention", "target": "transformers", "relation": "powers", "weight": 2, "tags": ["llm"]},
    {"source": "transformers", "target": "embedding", "relation": "co-occurs with", "weight": 1, "tags": ["cooccurrence"]},
]

GRAPH = build_graph(
    "doc-abc", "My Report.pdf", ENTITIES, EDGES,
    stats={"chunks": 3, "llm_edges": 1, "cooc_edges": 1},
    llm_enabled=True, created_at="2025-01-01T00:00:00+00:00",
)


def test_html_export_self_contained():
    html = render_html_export(GRAPH)
    assert "__TITLE__" not in html
    assert "My Report.pdf" in html
    assert "unpkg.com/force-graph" in html
    assert '"Attention"' in html  # graph JSON embedded
    assert '"relation_key"' in html
    assert '"confidence"' in html
    assert "UNDIRECTED ASSOCIATION" in html
    assert "CORE NETWORK" in html
    assert "ALL VISIBLE" in html
    assert ".width(el.clientWidth)" in html
    assert "createCommunityForce" in html
    assert "n_" in html  # node ids present
    # structure sanity
    assert "<!doctype html>" in html.lower()
    assert "GRAPH =" in html


def test_html_export_escapes_title():
    html = render_html_export({"document": {"name": 'A <script> & "Doc"'}, "nodes": [], "links": []})
    # the title text must be escaped (page legitimately contains its own <script> tags)
    assert "A &lt;script&gt; &amp; &quot;Doc&quot;" in html
    assert "<title>A <script>" not in html
    assert "<h1 title=\"A <script>" not in html


def test_html_export_escapes_embedded_json():
    # Document-derived node/snippet text is embedded as raw JSON inside the
    # page's <script> block — it must not be able to close that element.
    payload = '</script><script>alert(1)</script>'
    graph = {
        "document": {"name": "Doc"},
        "nodes": [{"id": "n_x", "name": payload, "type": "concept", "snippet": payload,
                   "degree": 0, "community": 0, "sources": [], "count": 1}],
        "links": [],
    }
    html = render_html_export(graph)
    assert payload not in html  # raw </script> sequence cannot appear from data
    assert "\\u003c/script" in html


def test_markdown_report_content():
    md = render_markdown_report(GRAPH)
    assert md.startswith("# My Report.pdf")
    assert "## Overview" in md
    assert "| Nodes | 3 |" in md
    assert "## Most-connected concepts" in md
    assert "**Attention**" in md
    assert "## Communities" in md
    assert "## Key relationships" in md
    assert "Attention | powers | Transformers" in md
    assert "Confidence" in md
    assert "schema" in md.lower()
    assert "correction overlays" in md
    assert "## Method" in md
    assert "LLM + statistical" in md


def test_markdown_report_statistical_mode():
    md = render_markdown_report(build_graph("d", "T", ENTITIES, EDGES, llm_enabled=False))
    assert "statistical only" in md
    assert "No LLM API key" in md


def test_csv_zip_contents():
    data = render_csv_zip(GRAPH)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert set(zf.namelist()) == {"nodes.csv", "edges.csv"}
        nodes = zf.read("nodes.csv").decode("utf-8")
        edges = zf.read("edges.csv").decode("utf-8")
    assert nodes.splitlines()[0] == "id,name,type,degree,community,sources,mentions,snippet"
    assert "Attention" in nodes
    assert edges.splitlines()[0] == (
        "source_id,source_name,target_id,target_name,relation,relation_key,original_relation,"
        "direction,kind,tag,provenance,weight,quality_score,confidence,support_count,evidence,snippet"
    )
    # names resolved in edges
    assert "Attention,powers,Transformers" in edges.replace(",", ",") or "Attention" in edges


# ── API endpoints ─────────────────────────────────────────────────────
def _upload_and_wait(path: Path) -> str:
    res = client.post(
        "/api/documents",
        files={"file": (path.name, path.read_bytes(), "application/octet-stream")},
    )
    assert res.status_code == 200
    doc_id = res.json()["doc_id"]
    deadline = time.time() + 20
    while time.time() < deadline:
        rec = client.get(f"/api/documents/{doc_id}/status").json()
        if rec["status"] in ("done", "error"):
            return doc_id if rec["status"] == "done" else None
        time.sleep(0.1)
    return None


def test_export_endpoints(sample_txt: Path):
    doc_id = _upload_and_wait(sample_txt)
    assert doc_id, "processing did not finish"

    r = client.get(f"/api/documents/{doc_id}/export/html")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "attachment" in r.headers["content-disposition"]
    assert "force-graph" in r.text

    r = client.get(f"/api/documents/{doc_id}/export/report")
    assert r.status_code == 200
    assert "text/markdown" in r.headers["content-type"]
    assert "## Overview" in r.text

    r = client.get(f"/api/documents/{doc_id}/export/csv")
    assert r.status_code == 200
    assert "application/zip" in r.headers["content-type"]
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert "nodes.csv" in zf.namelist()
        assert "edges.csv" in zf.namelist()


def test_export_missing_doc_404():
    assert client.get("/api/documents/nope/export/html").status_code == 404
    assert client.get("/api/documents/nope/export/report").status_code == 404
    assert client.get("/api/documents/nope/export/csv").status_code == 404
