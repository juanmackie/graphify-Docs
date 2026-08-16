"""Versioned graph relation/evidence/quality contract.

The graph API keeps the original ``tag``, ``snippet`` and ``weight`` fields for
backward compatibility. New links use the fields below so extraction quality
and future correction overlays can evolve without changing node/link identity.
"""
from __future__ import annotations

from typing import Final

GRAPH_SCHEMA_VERSION: Final[int] = 2
RELATION_SCHEMA_VERSION: Final[int] = 1

# Existing values remain valid. ``manual`` is reserved for the future correction
# overlay; this milestone only emits ``llm`` and ``cooccurrence``.
PROVENANCE_TAGS: Final[tuple[str, ...]] = ("llm", "cooccurrence", "manual")
DIRECTIONS: Final[tuple[str, ...]] = ("directed", "undirected")
RELATION_KINDS: Final[tuple[str, ...]] = ("assertion", "association")

# A link's stable, versioned shape. Optional values are represented as null or
# empty lists in JSON so old consumers can safely ignore them.
RELATION_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "source",
    "target",
    "relation",
    "relation_key",
    "original_relation",
    "relation_aliases",
    "direction",
    "kind",
    "tag",
    "provenance",
    "weight",
    "snippet",
    "evidence",
    "quality",
)

EVIDENCE_FIELDS: Final[tuple[str, ...]] = (
    "text",
    "source",
    "chunk_index",
    "paragraph_index",
    "sentence_index",
)

QUALITY_FIELDS: Final[tuple[str, ...]] = (
    "score",
    "confidence",
    "support_count",
    "endpoint_support",
    "evidence_count",
    "reasons",
)


def empty_quality() -> dict[str, object]:
    """Return the stable zero-value quality record for legacy links."""
    return {
        "score": 0.0,
        "confidence": 0.0,
        "support_count": 0,
        "endpoint_support": 0.0,
        "evidence_count": 0,
        "reasons": [],
    }


def empty_evidence() -> list[dict[str, object]]:
    """Return a fresh evidence list for a relation with no captured quote."""
    return []


def is_valid_direction(value: object) -> bool:
    return value in DIRECTIONS


def is_valid_kind(value: object) -> bool:
    return value in RELATION_KINDS


def schema_summary() -> dict[str, object]:
    """Machine-readable contract metadata exposed to tests and future clients."""
    return {
        "graph_schema_version": GRAPH_SCHEMA_VERSION,
        "relation_schema_version": RELATION_SCHEMA_VERSION,
        "relation_fields": list(RELATION_FIELDS),
        "evidence_fields": list(EVIDENCE_FIELDS),
        "quality_fields": list(QUALITY_FIELDS),
        "directions": list(DIRECTIONS),
        "kinds": list(RELATION_KINDS),
        "provenance_tags": list(PROVENANCE_TAGS),
    }
