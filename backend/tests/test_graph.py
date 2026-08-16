"""Tests for graph.builder + graph.community."""
from __future__ import annotations

from app.graph.builder import build_graph, edge_id, node_id
from app.graph.community import detect_communities
from app.graph.schema import GRAPH_SCHEMA_VERSION, RELATION_SCHEMA_VERSION, schema_summary

ENTITIES = [
    {"key": "alpha", "name": "Alpha", "type": "concept", "snippet": "sa", "count": 5, "sources": ["llm"]},
    {"key": "beta", "name": "Beta", "type": "concept", "snippet": "sb", "count": 3, "sources": ["llm"]},
    {"key": "gamma", "name": "Gamma", "type": "concept", "snippet": "", "count": 2, "sources": ["yake"]},
    {"key": "delta", "name": "Delta", "type": "keyword", "snippet": "", "count": 1, "sources": ["yake"]},
]

EDGES = [
    {"source": "alpha", "target": "beta", "relation": "links", "weight": 2, "tags": ["llm"]},
    {"source": "beta", "target": "gamma", "relation": "co-occurs with", "weight": 1, "tags": ["cooccurrence"]},
    {"source": "alpha", "target": "gamma", "relation": "mentions", "weight": 1, "tags": ["llm", "cooccurrence"]},
]


def test_graph_schema_is_versioned():
    summary = schema_summary()
    assert summary["graph_schema_version"] == GRAPH_SCHEMA_VERSION == 2
    assert summary["relation_schema_version"] == RELATION_SCHEMA_VERSION == 1
    assert "evidence" in summary["relation_fields"]
    assert "confidence" in summary["quality_fields"]
    assert summary["directions"] == ["directed", "undirected"]


def test_ids_are_stable():
    assert node_id("knowledge graph") == node_id("knowledge graph")
    assert len(node_id("knowledge graph")) > 5
    assert edge_id("a", "b", "r") == edge_id("a", "b", "r")
    assert node_id("a") != node_id("b")


def test_build_graph_schema():
    graph = build_graph("doc1", "My Doc", ENTITIES, EDGES, stats={"chunks": 4}, llm_enabled=True)
    assert graph["document"]["id"] == "doc1"
    assert graph["document"]["name"] == "My Doc"
    assert graph["document"]["llm_enabled"] is True
    assert graph["document"]["stats"]["chunks"] == 4
    assert graph["document"]["schema_version"] == 2
    assert graph["document"]["relation_schema_version"] == 1
    assert graph["document"]["stats"]["graph_schema_version"] == 2
    assert graph["document"]["stats"]["nodes"] == 4
    assert graph["document"]["stats"]["edges"] == 3

    node_ids = {n["id"] for n in graph["nodes"]}
    assert len(node_ids) == 4
    for link in graph["links"]:
        assert link["source"] in node_ids
        assert link["target"] in node_ids

    alpha = next(n for n in graph["nodes"] if n["name"] == "Alpha")
    assert alpha["degree"] == 2  # alpha-beta + alpha-gamma
    assert alpha["count"] == 5
    assert alpha["snippet"] == "sa"

    mixed = next(l for l in graph["links"] if l["relation"] == "mentions")
    assert mixed["tag"] == "both"
    assert mixed["direction"] == "directed"
    assert mixed["kind"] == "assertion"
    assert mixed["provenance"] == ["llm", "cooccurrence"]
    assert mixed["relation_key"] == "mentions"
    assert mixed["evidence"] == []
    assert mixed["quality"]["confidence"] == 0


def test_build_graph_degree_and_community():
    graph = build_graph("d", "T", ENTITIES, EDGES)
    by_name = {n["name"]: n for n in graph["nodes"]}
    assert by_name["Alpha"]["degree"] == 2
    assert by_name["Delta"]["degree"] == 0
    communities = {n["community"] for n in graph["nodes"]}
    assert len(communities) >= 1
    assert all(isinstance(n["community"], int) for n in graph["nodes"])


def test_build_graph_caps_nodes():
    graph = build_graph("d", "T", ENTITIES, EDGES, max_nodes=2)
    assert len(graph["nodes"]) == 2
    # Only alpha (deg 2) and beta (deg 2) survive; dangling edges dropped
    assert graph["document"]["stats"]["edges"] == 1
    names = {n["name"] for n in graph["nodes"]}
    assert "Alpha" in names and "Beta" in names


def test_build_graph_empty():
    graph = build_graph("d", "T", [], [])
    assert graph["nodes"] == []
    assert graph["links"] == []
    assert graph["document"]["stats"]["communities"] == 0


def test_detect_communities_two_clusters():
    entities = [
        {"key": "a"}, {"key": "b"}, {"key": "c"},
        {"key": "x"}, {"key": "y"},
    ]
    edges = [
        {"source": "a", "target": "b", "weight": 3},
        {"source": "b", "target": "c", "weight": 3},
        {"source": "a", "target": "c", "weight": 3},
        {"source": "x", "target": "y", "weight": 3},
    ]
    partition = detect_communities(entities, edges)
    assert partition["a"] == partition["b"] == partition["c"]
    assert partition["x"] == partition["y"]
    assert partition["a"] != partition["x"]


def test_detect_communities_isolated_nodes():
    partition = detect_communities([{"key": "a"}, {"key": "b"}], [])
    assert len(set(partition.values())) == 2
    assert partition["a"] != partition["b"]


def test_detect_communities_empty():
    assert detect_communities([], []) == {}
