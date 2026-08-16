"""In-process background job runner (single-user local app)."""
from __future__ import annotations

import threading
import traceback

from .pipeline import process_document
from .store import store

STALE_JOB_MESSAGE = "Interrupted by server restart — press RE-RUN to retry."


class JobManager:
    def __init__(self) -> None:
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def start(self, doc_id: str) -> bool:
        """Start processing doc_id in the background. Returns False if already running."""
        with self._lock:
            if doc_id in self._threads and self._threads[doc_id].is_alive():
                return False
            thread = threading.Thread(target=self._run, args=(doc_id,), daemon=True)
            self._threads[doc_id] = thread
            thread.start()
            return True

    def is_running(self, doc_id: str) -> bool:
        with self._lock:
            return doc_id in self._threads and self._threads[doc_id].is_alive()

    def mark_stale_on_startup(self) -> int:
        """Mark documents stuck in a non-terminal state as failed.

        Job threads are in-process and never survive a server restart, so any
        doc that isn't `done`/`error` after a restart is permanently stuck.
        Flagging it as `error` gives the UI a recovery path (RE-RUN) instead of
        an eternal progress spinner.
        """
        stale = [r for r in store.list_documents() if r["status"] not in ("done", "error")]
        for rec in stale:
            store.set_status(rec["id"], "error", progress=rec["progress"], error=STALE_JOB_MESSAGE)
        return len(stale)

    def _run(self, doc_id: str) -> None:
        try:
            process_document(doc_id)
        except Exception as exc:  # noqa: BLE001 - last-resort guard
            store.set_status(doc_id, "error", error=f"{type(exc).__name__}: {exc}")
            traceback.print_exc()
        finally:
            with self._lock:
                self._threads.pop(doc_id, None)


jobs = JobManager()
