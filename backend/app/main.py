"""FastAPI application — DocGraph backend API + static frontend serving."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .config import settings
from .jobs import jobs
from .store import store

app = FastAPI(title="DocGraph API", version="0.1.0")

# The dev server is the only cross-origin client. Production serves the SPA
# from this process, so an allowlist keeps unrelated local websites from
# issuing API requests to the user's document store.
LOCAL_FRONTEND_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_FRONTEND_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_doc_or_404(doc_id: str) -> dict:
    record = store.get(doc_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return record


def _require_ready(record: dict) -> dict:
    if record["status"] != "done":
        raise HTTPException(status_code=409, detail=f"Not ready (status: {record['status']}).")
    graph = store.load_graph(record["id"])
    if graph is None:
        raise HTTPException(status_code=404, detail="Graph not found.")
    return graph


def _sanitize_filename(name: str) -> str:
    base = Path(name).stem
    return re.sub(r"[^A-Za-z0-9._ -]+", "_", base).strip() or "document"


@app.on_event("startup")
def _mark_stale_jobs_on_startup() -> None:
    # Job threads never survive a restart; anything left mid-flight is stuck.
    jobs.mark_stale_on_startup()


# ── config / health ───────────────────────────────────────────────────
@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/config")
def config() -> dict:
    return {
        "has_api_key": settings.has_api_key,
        "model": settings.openai_model,
        "max_upload_mb": settings.max_upload_mb,
        "extraction_mode": settings.extraction_mode,
        "extraction_modes": ["fast", "balanced", "full"],
        "llm_concurrency": settings.llm_concurrency,
    }


# ── documents ─────────────────────────────────────────────────────────
@app.post("/api/documents")
async def upload(
    file: UploadFile = File(...),
    mode: str | None = Form(None),
) -> dict:
    name = file.filename or "document"
    ext = Path(name).suffix.lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext or '?'}'. "
            f"Supported: {', '.join(sorted(settings.allowed_extensions))}",
        )
    extraction_mode = (mode or settings.extraction_mode).strip().lower()
    if extraction_mode not in {"fast", "balanced", "full"}:
        raise HTTPException(status_code=400, detail="Extraction mode must be fast, balanced, or full.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_mb} MB upload limit.",
        )

    doc_id = store.create_document(name, ext, len(content), extraction_mode=extraction_mode)
    store.save_source(doc_id, content, ext)
    jobs.start(doc_id)
    return {"doc_id": doc_id, "name": name}


@app.get("/api/documents")
def list_documents() -> list[dict]:
    return store.list_documents()


@app.get("/api/documents/{doc_id}/status")
def document_status(doc_id: str) -> dict:
    return _get_doc_or_404(doc_id)


@app.get("/api/documents/{doc_id}/graph")
def document_graph(doc_id: str) -> dict:
    return _require_ready(_get_doc_or_404(doc_id))


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str) -> dict:
    _get_doc_or_404(doc_id)
    store.delete(doc_id)
    return {"ok": True}


@app.post("/api/documents/{doc_id}/reprocess")
def reprocess(doc_id: str) -> dict:
    """Re-run extraction for an existing document from its saved source file.

    Recovery path for jobs that died with a server restart (marked `error` on
    startup) or failed transiently — no need to re-upload a large file.
    """
    record = _get_doc_or_404(doc_id)
    source = store.source_path(doc_id, record["ext"])
    if not source.exists():
        raise HTTPException(
            status_code=409,
            detail="The source file is missing — upload the document again.",
        )
    if jobs.is_running(doc_id):
        raise HTTPException(
            status_code=409,
            detail="A job for this document is already running.",
        )
    previous = {key: record[key] for key in ("status", "progress", "error", "progress_detail")}
    store.update(doc_id, status="queued", progress=0.0, error=None, progress_detail=None)
    if not jobs.start(doc_id):
        # Another thread started a job first; undo the reset so the doc
        # doesn't sit in `queued` with no worker attached.
        store.update(doc_id, **previous)
        raise HTTPException(
            status_code=409,
            detail="A job for this document is already running.",
        )
    return {"doc_id": doc_id, "status": "queued"}


# ── exports ───────────────────────────────────────────────────────────
@app.get("/api/documents/{doc_id}/export/html")
def export_html(doc_id: str) -> Response:
    graph = _require_ready(_get_doc_or_404(doc_id))
    from .export.html import render_html_export

    content = render_html_export(graph)
    filename = f"{_sanitize_filename(graph['document']['name'])}-graph.html"
    return Response(
        content,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/documents/{doc_id}/export/report")
def export_report(doc_id: str) -> Response:
    graph = _require_ready(_get_doc_or_404(doc_id))
    from .export.report import render_markdown_report

    content = render_markdown_report(graph)
    filename = f"{_sanitize_filename(graph['document']['name'])}-report.md"
    return Response(
        content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/documents/{doc_id}/export/csv")
def export_csv(doc_id: str) -> Response:
    graph = _require_ready(_get_doc_or_404(doc_id))
    from .export.csv import render_csv_zip

    content = render_csv_zip(graph)
    filename = f"{_sanitize_filename(graph['document']['name'])}-csv.zip"
    return Response(
        content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── static frontend (production build) ────────────────────────────────
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
