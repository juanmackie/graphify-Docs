"""Tests for ingestion.parser."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.parser import (
    html_to_text,
    parse_document,
    parse_pdf,
    parse_txt,
)


def test_parse_txt(sample_txt: Path):
    parsed = parse_txt(sample_txt)
    assert "knowledge graph" in parsed.text.lower()
    assert parsed.format == "txt"
    assert parsed.words > 50


def test_parse_md(sample_md: Path):
    parsed = parse_document(sample_md)
    assert "knowledge graph" in parsed.text.lower()
    assert parsed.format == "txt"


def test_parse_pdf(sample_pdf: Path):
    parsed = parse_pdf(sample_pdf)
    assert "knowledge graph" in parsed.text.lower()
    assert parsed.pages >= 1
    assert parsed.format == "pdf"


def test_parse_docx(sample_docx: Path):
    parsed = parse_document(sample_docx)
    assert "entities" in parsed.text.lower()
    assert parsed.format == "docx"
    assert parsed.words > 50


def test_parse_pptx(sample_pptx: Path):
    parsed = parse_document(sample_pptx)
    assert "knowledge graph" in parsed.text.lower()
    assert parsed.format == "pptx"


def test_parse_html(sample_html: Path):
    parsed = parse_document(sample_html)
    assert "knowledge graph" in parsed.text.lower()
    # scripts/styles must be stripped
    assert "alert" not in parsed.text
    assert "color:red" not in parsed.text


def test_html_to_text_strips_tags():
    text = html_to_text("<div><h1>Title</h1><p>Hello <b>world</b>.</p></div>")
    assert "Title" in text and "Hello world" in text


def test_unsupported_extension(tmp_path: Path):
    path = tmp_path / "notes.xyz"
    path.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported file type"):
        parse_document(path)


def test_legacy_doc_rejected(tmp_path: Path):
    path = tmp_path / "old.doc"
    path.write_bytes(b"\xd0\xcf\x11\xe0 legacy binary")
    with pytest.raises(ValueError, match="docx"):
        parse_document(path)


def test_empty_text_raises(tmp_path: Path):
    path = tmp_path / "empty.txt"
    path.write_text("   \n\n  ", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        parse_document(path)


def test_cleanup_whitespace(sample_txt: Path):
    parsed = parse_document(sample_txt)
    assert "\n\n\n" not in parsed.text  # triple newlines collapsed
