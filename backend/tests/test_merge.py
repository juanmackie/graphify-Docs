"""Tests for extraction.merge."""
from __future__ import annotations

from app.extraction.merge import (
    merge_all,
    merge_edges,
    merge_entities,
    normalize_name,
    normalize_relation,
)


def test_normalize_name():
    assert normalize_name("AS 1851�2012") == "as 1851-2012"
    assert normalize_name("  Knowledge Graphs! ") == "knowledge graphs"
    assert normalize_name("The Transformer") == "transformer"
    assert normalize_name("An Entity") == "entity"
    assert normalize_name("A Graph") == "graph"
    assert normalize_name("Neo4j") == "neo4j"
    assert normalize_name("") == ""
    assert normalize_name("   ") == ""


def test_normalize_relation():
    assert normalize_relation(" Depends ON ") == "depends on"
    assert normalize_relation("Is-a-type-of.") == "is-a-type-of"


def test_merge_entities_dedup_and_best_spelling():
    raw = [
        {"name": "Knowledge Graph", "type": "concept", "snippet": "s1", "source": "llm"},
        {"name": "knowledge graph", "type": "concept", "snippet": "", "source": "llm"},
        {"name": "The knowledge graph", "type": "concept", "snippet": "s3", "source": "yake"},
        {"name": "Neo4j", "type": "technology", "snippet": "s4", "source": "llm"},
    ]
    entities = merge_entities(raw)
    assert len(entities) == 2
    kg = next(e for e in entities if e["key"] == "knowledge graph")
    assert kg["name"] == "Knowledge Graph"  # most common spelling
    assert kg["count"] == 3
    assert set(kg["sources"]) == {"llm", "yake"}
    assert kg["snippet"] == "s1"


def test_merge_entities_type_majority():
    raw = [
        {"name": "Neo4j", "type": "technology"},
        {"name": "neo4j", "type": "technology"},
        {"name": "Neo4j", "type": "organization"},
    ]
    entities = merge_entities(raw)
    assert entities[0]["type"] == "technology"


def test_merge_entities_sorted_by_count():
    raw = [
        {"name": "Rare"},
        {"name": "Common", "snippet": ""},
        {"name": "common", "snippet": ""},
        {"name": "common", "snippet": ""},
    ]
    entities = merge_entities(raw)
    assert entities[0]["key"] == "common"
    assert entities[1]["key"] == "rare"


def test_merge_edges_dedup_weight_tags():
    raw = [
        {"source": "A", "target": "B", "relation": "links", "tag": "llm", "weight": 1},
        {"source": "a", "target": "b", "relation": "Links", "tag": "llm", "weight": 1},
        {"source": "A", "target": "B", "relation": "links", "tag": "cooccurrence", "weight": 3},
        {"source": "A", "target": "A", "relation": "self", "tag": "llm"},  # self-loop dropped
        {"source": "", "target": "B", "relation": "bad", "tag": "llm"},  # empty dropped
    ]
    edges = merge_edges(raw)
    assert len(edges) == 1
    edge = edges[0]
    assert edge["source"] == "a" and edge["target"] == "b"
    assert edge["relation"] == "links"
    assert edge["weight"] == 5
    assert set(edge["tags"]) == {"llm", "cooccurrence"}


def test_merge_all_combines_and_filters_dangling():
    llm_entities = [{"name": "Attention", "type": "concept", "snippet": "sa"}]
    llm_relations = [
        {"source": "Attention", "target": "Transformer", "relation": "powers", "snippet": "sr"},
    ]
    keywords = [{"name": "Transformer"}]
    cooc = [{"source": "attention", "target": "transformer", "weight": 2}]
    result = merge_all(
        llm_entities=llm_entities,
        llm_relations=llm_relations,
        keywords=keywords,
        cooccurrence_edges=cooc,
    )
    names = {e["key"] for e in result["entities"]}
    assert names == {"attention", "transformer"}
    assert len(result["edges"]) == 2
    # both edges survive; one is the LLM relation, one the co-occurrence
    rels = {(e["source"], e["target"], e["relation"]) for e in result["edges"]}
    assert ("attention", "transformer", "powers") in rels
    assert ("attention", "transformer", "co-occurs with") in rels


def test_merge_all_filters_table_and_sentence_fragments():
    result = merge_all(
        llm_entities=[
            {"name": "Fire damper", "type": "concept"},
            {"name": "Damper fully open blades free to close and latch", "type": "concept"},
            {"name": "Records Result Pass", "type": "keyword"},
        ],
        llm_relations=[
            {
                "source": "Fire damper",
                "target": "Damper fully open blades free to close and latch",
                "relation": "requires",
            }
        ],
    )
    assert {entity["key"] for entity in result["entities"]} == {"fire damper"}
    assert result["edges"] == []


def test_merge_all_materializes_missing_relation_endpoint():
    result = merge_all(
        llm_entities=[{"name": "Only Entity", "type": "concept"}],
        llm_relations=[
            {
                "source": "Only Entity",
                "target": "Ghost",
                "relation": "mentions",
                "snippet": "Only Entity mentions Ghost.",
            }
        ],
    )
    assert {entity["key"] for entity in result["entities"]} == {"only entity", "ghost"}
    assert len(result["edges"]) == 1
    assert result["edges"][0]["quality"]["endpoint_support"] == 0.5


def test_merge_edges_canonicalizes_inverse_labels_and_preserves_evidence():
    edges = merge_edges(
        [
            {
                "source": "A",
                "target": "B",
                "relation": "uses",
                "tag": "llm",
                "snippet": "A uses B.",
                "evidence": [{"text": "A uses B.", "chunk_index": 1}],
            },
            {
                "source": "B",
                "target": "A",
                "relation": "is used by",
                "tag": "llm",
                "snippet": "B is used by A.",
                "evidence": [{"text": "B is used by A.", "chunk_index": 2}],
            },
        ]
    )
    assert len(edges) == 1
    edge = edges[0]
    assert (edge["source"], edge["target"]) == ("a", "b")
    assert edge["relation_key"] == "uses"
    assert edge["weight"] == 2
    assert set(edge["relation_aliases"]) == {"uses", "is used by"}
    assert len(edge["evidence"]) == 2
    assert set(edge["provenance"]) == {"llm"}
    assert edge["quality"]["confidence"] > 0
