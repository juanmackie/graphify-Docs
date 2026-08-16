"""LLM-based entity/relationship extraction via any OpenAI-compatible endpoint.

The pipeline calls :func:`extract_document` only when an API key is configured;
otherwise the graph is built from the statistical pass alone.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Condition, Lock
from typing import Callable

from json_repair import loads as json_repair_loads
from openai import OpenAI

from ..config import settings

SYSTEM_PROMPT = """You are an expert knowledge-graph extraction engine. Given a chunk of a document, extract the important named entities / concepts and the typed relationships between them.

Return ONLY valid JSON with exactly this shape (no markdown, no commentary):

{
  "entities": [
    {"name": "exact entity name as it appears", "type": "concept|person|organization|place|technology|method|event|product|other", "snippet": "verbatim short quote from the text (<=200 chars)"}
  ],
  "relations": [
    {
      "source": "entity name",
      "target": "entity name",
      "relation": "short semantic phrase like 'depends on', 'is a type of', 'causes', 'mentions', 'part of', 'improves'",
      "direction": "directed",
      "kind": "assertion",
      "snippet": "verbatim short quote supporting this relation (<=200 chars)",
      "evidence": [{"text": "the same or another verbatim supporting quote (<=300 chars)"}]
    }
  ]
}

Rules:
- Only include entities and relations supported by the chunk text. Names must match the text's spelling.
- Reuse the same name for the same entity everywhere. A relation endpoint may be included even if it was not important enough for the entities list.
- Typed semantic relations are normally directed assertions: source performs or has the relation toward target. Use kind `association` and direction `undirected` only when the text supports a genuinely symmetric association rather than a directional claim.
- Use a concise semantic relation phrase, not a sentence. Keep the original subject/object order for directed relations.
- 5 to 25 entities and 5 to 30 relations, most important first.
- Each snippet/evidence text must be a verbatim, short quote from the text. Do not invent evidence.
- Do not output anything outside the JSON object."""


def build_user_prompt(chunk: str, chunk_index: int) -> str:
    return (
        f"Extract the knowledge graph from this chunk (chunk {chunk_index}).\n\n"
        f"<chunk>\n{chunk}\n</chunk>"
    )


# ── robust JSON parsing ───────────────────────────────────────────────
def _repair_json(text: str) -> dict | None:
    """Best-effort repairs for common LLM JSON mistakes, then parse.

    Uses the `json-repair` library (handles trailing commas, unquoted
    keys/values, single quotes, truncated JSON, ...). Returns None when
    the repaired value isn't a JSON object.
    """
    try:
        parsed = json_repair_loads(text)
    except Exception as exc:  # noqa: BLE001 - last-resort parser for untrusted LLM output
        return None
    return parsed if isinstance(parsed, dict) else None


def _extract_json(text: str) -> dict | None:
    """Pull the first balanced JSON object out of *text*."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = text[start : end + 1]
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return _repair_json(candidate)


def _clean_str(value: object, max_len: int = 500) -> str:
    if not isinstance(value, str):
        value = str(value or "")
    return value.strip()[:max_len]


def _clean_index(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        index = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return index if index >= 0 else None


def _parse_evidence(value: object, fallback: str = "") -> list[dict]:
    """Normalize new evidence arrays while accepting old snippet-only output."""
    items: list[dict] = []
    values = value if isinstance(value, list) else ([value] if value else [])
    for item in values:
        if isinstance(item, str):
            text = _clean_str(item, 300)
            metadata: dict = {}
        elif isinstance(item, dict):
            text = _clean_str(item.get("text") or item.get("quote") or item.get("snippet"), 300)
            metadata = item
        else:
            continue
        if not text:
            continue
        evidence = {"text": text}
        for output_key, *input_keys in (
            ("chunk_index", "chunk_index", "chunk"),
            ("paragraph_index", "paragraph_index", "paragraph"),
            ("sentence_index", "sentence_index", "sentence"),
        ):
            for input_key in input_keys:
                index = _clean_index(metadata.get(input_key))
                if index is not None:
                    evidence[output_key] = index
                    break
        if evidence not in items:
            items.append(evidence)
    if not items and fallback:
        items.append({"text": _clean_str(fallback, 300)})
    return items[:8]


def parse_llm_response(content: str) -> dict | None:
    """Parse a raw model response into {entities, relations} or None if invalid."""
    data = _extract_json(content)
    if data is None:
        return None

    entities: list[dict] = []
    for ent in data.get("entities") or []:
        if not isinstance(ent, dict):
            continue
        name = _clean_str(ent.get("name"))
        if not name:
            continue
        entities.append(
            {
                "name": name,
                "type": _clean_str(ent.get("type")) or "concept",
                "snippet": _clean_str(ent.get("snippet"), 300),
            }
        )

    relations: list[dict] = []
    for rel in data.get("relations") or data.get("relationships") or []:
        if not isinstance(rel, dict):
            continue
        source = _clean_str(rel.get("source"))
        target = _clean_str(rel.get("target"))
        relation = _clean_str(rel.get("relation"))
        if not source or not target or not relation or source.lower() == target.lower():
            continue
        original_relation = relation
        direction = _clean_str(rel.get("direction"), 30).lower() or "directed"
        if direction not in {"directed", "undirected"}:
            direction = "directed"
        kind = _clean_str(rel.get("kind") or rel.get("relation_kind"), 30).lower()
        if kind not in {"assertion", "association"}:
            kind = "association" if direction == "undirected" else "assertion"
        snippet = _clean_str(rel.get("snippet"), 300)
        relations.append(
            {
                "source": source,
                "target": target,
                "relation": relation.lower(),
                "original_relation": original_relation,
                "direction": direction,
                "kind": kind,
                "snippet": snippet,
                "evidence": _parse_evidence(rel.get("evidence"), fallback=snippet),
            }
        )

    return {"entities": entities[:30], "relations": relations[:40]}


# ── OpenAI-compatible client ──────────────────────────────────────────
def _is_throttle_error(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if status in {408, 429} or (isinstance(status, int) and status >= 500):
        return True
    name = type(exc).__name__.lower()
    return any(token in name for token in ("timeout", "connection", "rate_limit"))


class AdaptiveRateLimiter:
    """A cooperative limiter shared by all extraction workers.

    It starts at the configured concurrency, halves capacity after a provider
    throttle, applies jitter-free cooldown spacing, and increases capacity one
    slot at a time after a sustained run of successful requests.
    """

    def __init__(self, maximum: int) -> None:
        self.maximum = max(1, maximum)
        self.allowed = self.maximum
        self.active = 0
        self.successes = 0
        self.throttle_events = 0
        self.next_request_at = 0.0
        self.cooldown_seconds = 0.0
        self.condition = Condition()

    def acquire(self) -> None:
        while True:
            with self.condition:
                now = time.monotonic()
                wait_for = self.next_request_at - now
                if self.active < self.allowed and wait_for <= 0:
                    self.active += 1
                    return
                if wait_for > 0:
                    pass
                else:
                    self.condition.wait(timeout=0.25)
                    continue
            time.sleep(min(wait_for, 1.0))

    def release(self, exc: Exception | None = None) -> None:
        with self.condition:
            self.active = max(0, self.active - 1)
            if exc is not None and _is_throttle_error(exc):
                self.throttle_events += 1
                self.allowed = max(1, self.allowed // 2)
                self.successes = 0
                self.cooldown_seconds = min(8.0, max(0.5, self.cooldown_seconds * 2 or 0.5))
                self.next_request_at = max(
                    self.next_request_at,
                    time.monotonic() + self.cooldown_seconds,
                )
            elif exc is None:
                self.successes += 1
                if self.successes >= max(4, self.allowed * 2):
                    self.allowed = min(self.maximum, self.allowed + 1)
                    self.successes = 0
                    self.cooldown_seconds = 0.0
            self.condition.notify_all()

    def snapshot(self) -> dict[str, int]:
        with self.condition:
            return {
                "effective_concurrency": self.allowed,
                "throttle_events": self.throttle_events,
            }


def _make_client(http_client=None) -> OpenAI:
    """Client with a bounded per-request timeout.

    A hung upstream must fail fast (and be counted as an llm_error) instead of
    pinning the job in EXTRACT for the SDK default of 10 minutes per call ×
    retries. Both knobs are env-tunable: LLM_TIMEOUT_SECONDS, LLM_MAX_RETRIES.
    """
    return OpenAI(
        api_key=settings.openai_api_key or "sk-local-placeholder",
        base_url=settings.openai_base_url,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        http_client=http_client,
    )


def _create(
    client: OpenAI,
    messages: list[dict],
    use_json_mode: bool,
    rate_limiter: AdaptiveRateLimiter | None = None,
):
    kwargs: dict = {
        "model": settings.openai_model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 4000,
    }
    if use_json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    def call() -> object:
        if rate_limiter is not None:
            rate_limiter.acquire()
        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as exc:
            if rate_limiter is not None:
                rate_limiter.release(exc)
            raise
        else:
            if rate_limiter is not None:
                rate_limiter.release()
            return response

    try:
        return call()
    except Exception as exc:
        if not use_json_mode or _is_throttle_error(exc):
            raise
        # Some OpenAI-compatible servers reject response_format — retry without it.
        kwargs.pop("response_format", None)
        return call()


def extract_chunk(
    client: OpenAI,
    chunk: str,
    chunk_index: int,
    rate_limiter: AdaptiveRateLimiter | None = None,
) -> dict:
    """Extract entities+relations from one chunk. Returns partial result on failure."""
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(chunk, chunk_index)},
    ]
    for _attempt in range(2):
        try:
            response = _create(client, messages, use_json_mode=True, rate_limiter=rate_limiter)
            content = response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001 - provider/network errors handled by caller
            return {"entities": [], "relations": [], "chunk": chunk_index, "error": str(exc)}

        parsed = parse_llm_response(content)
        if parsed is not None:
            parsed["chunk"] = chunk_index
            # Attach the source chunk to every relation/evidence item. This is
            # additive and lets old mocked responses gain explainable evidence.
            for relation in parsed.get("relations", []):
                relation["chunk"] = chunk_index
                for evidence in relation.get("evidence", []):
                    evidence.setdefault("chunk_index", chunk_index)
            return parsed
        # One repair attempt: tell the model its output was invalid.
        messages.append({"role": "assistant", "content": content})
        messages.append(
            {
                "role": "user",
                "content": "Your previous response was not valid JSON. Return ONLY a valid JSON object "
                "with 'entities' and 'relations' keys — no markdown or prose.",
            }
        )
    return {"entities": [], "relations": [], "chunk": chunk_index, "error": "unparseable response"}


def _chunk_cache_key(chunk: str, model: str) -> str:
    prompt_hash = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:16]
    payload = f"v2|{model}|{prompt_hash}|{chunk}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class _CheckpointStore:
    def __init__(self, path: Path | str | None, model: str) -> None:
        self.path = Path(path) if path else None
        self.model = model
        self.lock = Lock()
        self.items: dict[str, dict] = {}
        if self.path and self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if data.get("schema") == 1:
                    self.items = data.get("items", {})
            except (OSError, ValueError, TypeError):
                self.items = {}

    def get(self, key: str) -> dict | None:
        with self.lock:
            value = self.items.get(key)
            return dict(value) if isinstance(value, dict) else None

    def save(self, key: str, result: dict) -> None:
        if not self.path or result.get("error"):
            return
        with self.lock:
            self.items[key] = result
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(self.path.suffix + ".tmp")
            temp.write_text(
                json.dumps({"schema": 1, "model": self.model, "items": self.items}, ensure_ascii=False),
                encoding="utf-8",
            )
            temp.replace(self.path)


def extract_document(
    chunks: list[str],
    progress_cb: Callable[[float], None] | None = None,
    http_client=None,
    chunk_indices: list[int] | None = None,
    concurrency: int | None = None,
    checkpoint_path: Path | str | None = None,
    progress_detail_cb: Callable[[dict], None] | None = None,
) -> dict:
    """Run bounded-concurrent LLM extraction over the supplied chunks.

    Results are consumed in source order for deterministic output while network
    calls overlap. Returns extraction results plus timing/concurrency metrics.
    """
    if not settings.has_api_key:
        return {"entities": [], "relations": [], "llm_used": False, "llm_errors": 0, "llm_chunks": 0}
    if not chunks:
        return {"entities": [], "relations": [], "llm_used": True, "llm_errors": 0, "llm_chunks": 0}

    model = getattr(settings, "openai_model", "unknown")
    checkpoint = _CheckpointStore(checkpoint_path, model)
    client = _make_client(http_client)
    entities: list[dict] = []
    relations: list[dict] = []
    errors = 0
    total = len(chunks)
    started = time.perf_counter()
    chunk_indices = chunk_indices or list(range(total))
    if len(chunk_indices) != total:
        raise ValueError("chunk_indices must have one entry per chunk")
    configured_concurrency = getattr(settings, "llm_concurrency", 1)
    worker_count = max(1, min(int(concurrency or configured_concurrency), total))
    active = 0
    max_active = 0
    active_lock = Lock()
    rate_limiter = AdaptiveRateLimiter(worker_count)
    results: dict[int, dict] = {}
    chunk_seconds: dict[int, float] = {}
    pending: list[int] = []
    cache_hits = 0

    for position, chunk in enumerate(chunks):
        key = _chunk_cache_key(chunk, model)
        cached = checkpoint.get(key)
        if cached is not None and not cached.get("error"):
            cached["chunk"] = chunk_indices[position]
            results[position] = cached
            cache_hits += 1
        else:
            pending.append(position)

    def run_one(position: int) -> tuple[int, dict, float]:
        nonlocal active, max_active
        with active_lock:
            active += 1
            max_active = max(max_active, active)
        chunk_started = time.perf_counter()
        try:
            result = extract_chunk(
                client,
                chunks[position],
                chunk_indices[position],
                rate_limiter=rate_limiter,
            )
            if not result.get("error"):
                checkpoint.save(_chunk_cache_key(chunks[position], model), result)
            return position, result, time.perf_counter() - chunk_started
        finally:
            with active_lock:
                active -= 1

    completed = cache_hits
    if completed and progress_cb:
        progress_cb(completed / total)
    if completed and progress_detail_cb:
        progress_detail_cb({"completed": completed, "total": total, "cache_hits": cache_hits, "cache_misses": len(pending), "eta_seconds": 0.0, "throttle_events": 0})

    # Each worker writes its checkpoint immediately. Completion callbacks use
    # as_completed so the UI reflects actual work rather than input ordering.
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="llm") as executor:
        futures = [executor.submit(run_one, position) for position in pending]
        for future in as_completed(futures):
            position, result, request_seconds = future.result()
            results[position] = result
            chunk_seconds[position] = request_seconds
            completed += 1
            observed = list(chunk_seconds.values())
            average = sum(observed) / len(observed) if observed else 0.0
            effective = rate_limiter.snapshot()["effective_concurrency"]
            eta = average * max(0, total - completed) / max(1, effective)
            if progress_cb:
                progress_cb(completed / total)
            if progress_detail_cb:
                progress_detail_cb({
                    "completed": completed,
                    "total": total,
                    "cache_hits": cache_hits,
                    "cache_misses": len(pending),
                    "eta_seconds": round(eta, 1),
                    "concurrency": effective,
                    "throttle_events": rate_limiter.snapshot()["throttle_events"],
                })

    for position in range(total):
        result = results[position]
        entities.extend(result.get("entities", []))
        relations.extend(result.get("relations", []))
        if result.get("error"):
            errors += 1

    elapsed = time.perf_counter() - started
    measured_seconds = list(chunk_seconds.values())
    return {
        "entities": entities,
        "relations": relations,
        "llm_used": True,
        "llm_errors": errors,
        "llm_chunks": total,
        "llm_cache_hits": cache_hits,
        "llm_cache_misses": len(pending),
        "llm_seconds": round(elapsed, 3),
        "llm_avg_chunk_seconds": round(sum(measured_seconds) / len(measured_seconds), 3) if measured_seconds else 0.0,
        "llm_max_chunk_seconds": round(max(measured_seconds), 3) if measured_seconds else 0.0,
        "llm_concurrency": worker_count,
        "llm_max_active": max_active,
        "llm_effective_concurrency": rate_limiter.snapshot()["effective_concurrency"],
        "llm_throttle_events": rate_limiter.snapshot()["throttle_events"],
    }
