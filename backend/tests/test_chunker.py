"""Tests for ingestion.chunker."""
from __future__ import annotations

from app.ingestion.chunker import chunk_text


def test_empty_text_returns_empty_list():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_single_short_paragraph():
    chunks = chunk_text("Hello world.")
    assert len(chunks) == 1
    assert chunks[0] == "Hello world."


def test_respects_max_chars():
    text = "\n\n".join(f"Paragraph number {i} with some filler words " * 20 for i in range(10))
    chunks = chunk_text(text, max_chars=2000, overlap_chars=200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 2500  # small slack for overlong single sentences


def test_consecutive_chunks_overlap():
    text = "\n\n".join(f"Section {i}: " + "alpha beta gamma delta epsilon " * 60 for i in range(8))
    chunks = chunk_text(text, max_chars=1500, overlap_chars=200)
    assert len(chunks) >= 2
    for prev, nxt in zip(chunks, chunks[1:]):
        tail = prev[-200:]
        # some word from the previous tail should reappear at the start of next chunk
        words = set(tail.split())
        assert words & set(nxt.split()), "expected overlap between consecutive chunks"


def test_combines_small_paragraphs():
    paras = ["One. Two.", "Three. Four.", "Five."]
    text = "\n\n".join(paras)
    chunks = chunk_text(text, max_chars=10000)
    assert len(chunks) == 1
    assert "One." in chunks[0] and "Five." in chunks[0]


def test_reconstructs_all_content():
    paras = [f"Paragraph {i} content words here. " * 30 for i in range(12)]
    text = "\n\n".join(paras)
    chunks = chunk_text(text, max_chars=2000, overlap_chars=250)
    for para in paras:
        # every paragraph should be present in full (modulo edge whitespace) in at least one chunk
        assert any(para.strip() in c for c in chunks)


def test_overlap_clamped_to_half():
    text = "word " * 5000
    chunks = chunk_text(text, max_chars=2000, overlap_chars=5000)
    assert len(chunks) >= 2
