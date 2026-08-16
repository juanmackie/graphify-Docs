"""Tests for extraction.statistical."""
from __future__ import annotations

from app.extraction.statistical import (
    _in_text,
    cooccurrence_edges,
    document_link_candidates,
    extract_keywords,
    normalize_keyword,
)


def test_normalize_keyword():
    assert normalize_keyword("  Knowledge Graphs! ") == "knowledge graphs"
    assert normalize_keyword('"Neo4j"') == "neo4j"
    assert normalize_keyword("multiple   spaces") == "multiple spaces"


def test_in_text_word_boundary():
    assert _in_text("graph", "a knowledge graph maps entities")
    assert not _in_text("graph", "a paragraph explains it")  # not substring
    assert _in_text("graph", "paragraph about graph databases")
    assert _in_text("knowledge graph", "this knowledge graph is nice")


def test_extract_keywords_from_sample(sample_text: str):
    keywords = extract_keywords(sample_text, max_keywords=30)
    assert len(keywords) >= 5
    # sorted by score ascending (better first)
    scores = [k.score for k in keywords]
    assert scores == sorted(scores)
    # normalized + meaningful
    assert all(k.name == k.name.lower() for k in keywords)
    assert all(len(k.name) >= 3 for k in keywords)
    names = [k.name for k in keywords]
    assert "knowledge graph" in names or "knowledge graphs" in names


def test_extract_keywords_empty():
    assert extract_keywords("") == []
    assert extract_keywords("   ") == []


def test_keyword_counts():
    text = "Graphs are great. Graphs connect things. Graphs repeat graphs."
    keywords = extract_keywords(text, max_keywords=5)
    graph_kw = next((k for k in keywords if k.name == "graphs"), None)
    assert graph_kw is not None
    assert graph_kw.count == 4


def test_cooccurrence_edges_weights():
    chunks = [
        "attention mechanism powers transformers",
        "attention is the core of transformers",
        "attention and transformers improve translation",
        "unrelated sentence about gardening and trees",
    ]
    keywords = [
        {"name": "attention"},
        {"name": "transformers"},
        {"name": "gardening"},
        {"name": "trees"},
    ]
    from app.extraction.statistical import Keyword

    kws = [Keyword(**k) for k in keywords]
    edges = cooccurrence_edges(chunks, kws, min_weight=1)
    by_name = {(e["source"], e["target"]): e["weight"] for e in edges}
    assert by_name.get(("attention", "transformers")) == 3
    # gardening + trees co-occur in exactly one chunk
    assert by_name.get(("gardening", "trees")) == 1


def test_cooccurrence_min_weight_filter():
    chunks = ["alpha beta", "alpha beta", "beta gamma"]
    keywords = [{"name": "alpha"}, {"name": "beta"}, {"name": "gamma"}]
    from app.extraction.statistical import Keyword

    kws = [Keyword(**k) for k in keywords]
    edges = cooccurrence_edges(chunks, kws, min_weight=2)
    pairs = {(e["source"], e["target"]) for e in edges}
    assert ("alpha", "beta") in pairs  # weight 2
    assert ("beta", "gamma") not in pairs  # weight 1 < min_weight


def test_document_link_candidates_are_deterministic_and_validate_endpoints():
    text = (
        "Alpha improves Beta.\n\n"
        "Gamma is discussed here.\n\n"
        "Alpha and Gamma remain associated."
    )
    entities = ["Alpha", "Beta", "Gamma", "Ghost"]
    first = document_link_candidates(text, entities)
    second = document_link_candidates(text, entities)
    assert first == second
    pairs = {(edge["source"], edge["target"]) for edge in first}
    assert {("alpha", "beta"), ("alpha", "gamma"), ("beta", "gamma")} <= pairs
    assert all("ghost" not in pair for pair in pairs)
    edge = next(edge for edge in first if edge["target"] == "beta")
    assert edge["direction"] == "undirected"
    assert edge["kind"] == "association"
    assert edge["tag"] == "cooccurrence"
    assert edge["support_count"] >= 1
    assert edge["evidence"][0]["source"] == "cooccurrence"
    assert "Alpha" in edge["evidence"][0]["text"]


def test_document_link_candidates_recover_adjacent_sentence_window():
    text = "Alpha is important. Beta is discussed next."
    edges = document_link_candidates(text, ["alpha", "beta"])
    assert len(edges) == 1
    assert edges[0]["window_support"] >= 1
    assert edges[0]["sentence_support"] == 0
    assert edges[0]["weight"] >= 2


def test_document_link_candidates_respect_pdf_line_locality():
    text = "\n".join(
        [
            "Alpha",
            "Beta",
            "Gamma",
            "Delta",
            "Epsilon",
            "Zeta",
            "Eta",
            "Theta",
            "Iota",
            "Kappa",
            "Lambda",
            "Mu",
            "Nu",
            "Xi",
            "Omicron",
            "Pi",
            "Rho",
            "Sigma",
            "Tau",
            "Upsilon",
            "Phi",
            "Chi",
            "Psi",
            "Omega",
        ]
    )
    edges = document_link_candidates(text, ["alpha", "delta", "omega"])
    pairs = {(edge["source"], edge["target"]) for edge in edges}
    assert ("alpha", "omega") not in pairs


def test_cooccurrence_no_edges_for_empty():
    assert cooccurrence_edges([], []) == []
    assert cooccurrence_edges(["a b c"], []) == []
