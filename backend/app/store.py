"""Local storage: sqlite3 index + per-document directories under DATA_DIR/uploads/{doc_id}/."""
from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings

_UNSET = object()


class Store:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.uploads_dir = self.data_dir / "uploads"
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "documents.db"
        self._init_db()

    # ── low-level db helpers ──────────────────────────────────────────
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id          TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    ext         TEXT NOT NULL,
                    size        INTEGER NOT NULL,
                    status      TEXT NOT NULL,
                    extraction_mode TEXT NOT NULL DEFAULT 'balanced',
                    progress_detail TEXT,
                    progress    REAL NOT NULL DEFAULT 0,
                    error       TEXT,
                    node_count  INTEGER NOT NULL DEFAULT 0,
                    edge_count  INTEGER NOT NULL DEFAULT 0,
                    stats_json  TEXT,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                )
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
            if "extraction_mode" not in columns:
                conn.execute(
                    "ALTER TABLE documents ADD COLUMN extraction_mode TEXT NOT NULL DEFAULT 'balanced'"
                )
            if "progress_detail" not in columns:
                conn.execute("ALTER TABLE documents ADD COLUMN progress_detail TEXT")

    # ── documents CRUD ────────────────────────────────────────────────
    def create_document(
        self, name: str, ext: str, size: int, extraction_mode: str = "balanced"
    ) -> str:
        doc_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        (self.uploads_dir / doc_id).mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO documents (id, name, ext, size, status, extraction_mode, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 'queued', ?, ?, ?)",
                (doc_id, name, ext, size, extraction_mode, now, now),
            )
        return doc_id

    def update(self, doc_id: str, **fields: Any) -> None:
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._conn() as conn:
            conn.execute(f"UPDATE documents SET {cols} WHERE id=?", (*fields.values(), doc_id))

    def set_status(
        self,
        doc_id: str,
        status: str,
        progress: float | None = None,
        error: str | None | object = _UNSET,
    ) -> None:
        fields: dict[str, Any] = {"status": status}
        if progress is not None:
            fields["progress"] = progress
        if error is not _UNSET:
            fields["error"] = error
        self.update(doc_id, **fields)

    def get(self, doc_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        return dict(row) if row else None

    def list_documents(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def delete(self, doc_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        shutil.rmtree(self.uploads_dir / doc_id, ignore_errors=True)

    # ── per-document files ────────────────────────────────────────────
    def doc_dir(self, doc_id: str) -> Path:
        return self.uploads_dir / doc_id

    def source_path(self, doc_id: str, ext: str) -> Path:
        return self.doc_dir(doc_id) / f"source{ext}"

    def save_source(self, doc_id: str, content: bytes, ext: str) -> Path:
        path = self.source_path(doc_id, ext)
        path.write_bytes(content)
        return path

    def save_text(self, doc_id: str, text: str) -> Path:
        path = self.doc_dir(doc_id) / "text.txt"
        path.write_text(text, encoding="utf-8")
        return path

    def load_text(self, doc_id: str) -> str | None:
        path = self.doc_dir(doc_id) / "text.txt"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def save_graph(self, doc_id: str, graph: dict[str, Any]) -> Path:
        path = self.doc_dir(doc_id) / "graph.json"
        path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_graph(self, doc_id: str) -> dict[str, Any] | None:
        path = self.doc_dir(doc_id) / "graph.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_meta(self, doc_id: str, meta: dict[str, Any]) -> Path:
        """Raw extraction results (chunks, entities, edges) — used by exports and re-runs."""
        path = self.doc_dir(doc_id) / "meta.json"
        path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load_meta(self, doc_id: str) -> dict[str, Any] | None:
        path = self.doc_dir(doc_id) / "meta.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


store = Store(settings.data_dir)
