"""Paragraph-aware chunking with overlap for LLM + statistical extraction."""
from __future__ import annotations

import re

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


def _tail(text: str, chars: int) -> str:
    """Keep the trailing `chars` characters of *text*, snapped to a word boundary."""
    if len(text) <= chars:
        return text
    tail = text[-chars:]
    # snap forward to next space so we don't cut mid-word
    nxt = tail.find(" ")
    if 0 < nxt < 20:
        tail = tail[nxt + 1 :]
    return tail.strip()


def _split_paragraph(paragraph: str, max_chars: int) -> list[str]:
    """Split one paragraph into pieces no larger than max_chars (sentence-aware)."""
    if len(paragraph) <= max_chars:
        return [paragraph]
    sentences = [s.strip() for s in _SENTENCE_END.split(paragraph) if s.strip()]
    pieces: list[str] = []
    current = ""
    for sent in sentences:
        if len(sent) > max_chars:
            # hard-split an overlong sentence
            for i in range(0, len(sent), max_chars):
                pieces.append(sent[i : i + max_chars].strip())
            current = ""
            continue
        if current and len(current) + len(sent) + 1 > max_chars:
            pieces.append(current.strip())
            current = sent
        else:
            current = f"{current} {sent}" if current else sent
    if current:
        pieces.append(current.strip())
    return pieces or [paragraph[:max_chars]]


def chunk_text(text: str, max_chars: int = 4000, overlap_chars: int = 200) -> list[str]:
    """Split *text* into overlapping chunks at paragraph boundaries.

    - Paragraphs are delimited by blank lines.
    - Consecutive paragraphs are merged until max_chars, then the previous
      chunk's tail (overlap_chars) is carried into the next chunk so entity
      mentions spanning a boundary stay visible to both chunks.
    """
    if not text or not text.strip():
        return []
    max_chars = max(500, int(max_chars))
    overlap_chars = min(max(0, int(overlap_chars)), max_chars // 2)

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        for part in _split_paragraph(para, max_chars):
            if current and len(current) + len(part) + 2 > max_chars:
                chunks.append(current)
                current = _tail(current, overlap_chars)
            current = f"{current}\n\n{part}" if current else part

    if current:
        chunks.append(current)
    return [c for c in chunks if c.strip()]
