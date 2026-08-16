"""Adaptive selection of representative LLM chunks.

Statistical extraction still sees the complete document. This module only
reduces the expensive remote-LLM workload while retaining section coverage and
preferring chunks with distinctive terms and useful headings.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
_HEADING_RE = re.compile(r"^(?:#{1,6}\s+|\d+(?:\.\d+)*[.)]?\s+|[A-Z][A-Z0-9][A-Z0-9 \-:]{4,})")


@dataclass(frozen=True)
class ChunkSelection:
    chunks: list[str]
    indices: list[int]
    scores: list[float]
    total: int
    mode: str


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def _target_count(total: int, mode: str, fraction: float, minimum: int, maximum: int) -> int:
    if total == 0:
        return 0
    if mode == "full" or total <= minimum:
        return total
    if mode == "fast":
        fraction = min(fraction, 0.2)
    elif mode != "balanced":
        mode = "balanced"
    target = math.ceil(total * max(0.05, fraction))
    return min(total, max(1, min(maximum, max(minimum, target))))


def select_chunks(
    chunks: list[str],
    *,
    mode: str = "balanced",
    fraction: float = 0.35,
    minimum: int = 12,
    maximum: int = 250,
) -> ChunkSelection:
    """Select representative chunks with deterministic section coverage.

    At least one chunk is selected from each coarse document section whenever
    possible. Remaining slots go to high-scoring chunks based on headings,
    distinctive vocabulary, and useful chunk length.
    """
    total = len(chunks)
    if not chunks:
        return ChunkSelection([], [], [], 0, mode)
    normalized_mode = mode.lower().strip()
    target = _target_count(total, normalized_mode, fraction, minimum, maximum)
    if target == total:
        return ChunkSelection(chunks[:], list(range(total)), [1.0] * total, total, normalized_mode)

    token_lists = [_tokens(chunk) for chunk in chunks]
    document_frequency: dict[str, int] = {}
    for tokens in token_lists:
        for token in set(tokens):
            document_frequency[token] = document_frequency.get(token, 0) + 1

    scored: list[tuple[float, int]] = []
    for index, (chunk, tokens) in enumerate(zip(chunks, token_lists)):
        if not tokens:
            scored.append((0.0, index))
            continue
        rare_terms = sum(1.0 / document_frequency[token] for token in set(tokens))
        distinctiveness = rare_terms / max(1.0, math.sqrt(len(tokens)))
        heading_bonus = 1.0 if any(_HEADING_RE.match(line.strip()) for line in chunk.splitlines()[:5]) else 0.0
        length_score = min(1.0, len(tokens) / 350.0)
        score = distinctiveness + heading_bonus + length_score * 0.15
        scored.append((score, index))

    ranked = sorted(scored, key=lambda item: (-item[0], item[1]))
    selected: set[int] = set()
    # Divide the document into target-sized sections and reserve coverage slots.
    section_count = min(target, max(1, round(math.sqrt(total))))
    for section in range(section_count):
        start = (section * total) // section_count
        end = ((section + 1) * total) // section_count
        candidates = [(score, index) for score, index in scored if start <= index < end]
        if candidates:
            selected.add(max(candidates, key=lambda item: (item[0], -item[1]))[1])

    for _score, index in ranked:
        if len(selected) >= target:
            break
        selected.add(index)

    indices = sorted(selected)
    score_map = {index: score for score, index in scored}
    return ChunkSelection(
        chunks=[chunks[index] for index in indices],
        indices=indices,
        scores=[round(score_map[index], 5) for index in indices],
        total=total,
        mode=normalized_mode,
    )
