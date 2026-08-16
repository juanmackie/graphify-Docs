"""Assemble the final graph.json consumed by the frontend and the exporters."""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any

from .community import detect_communities
from .schema import (
    GRAPH_SCHEMA_VERSION,
    RELATION_SCHEMA_VERSION,
    empty_quality,
)


def node_id(key: str) -> str:
    return "n_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def edge_id(source: str, target: str, relation: str) -> str:
    return "e_" + hashlib.sha1(f"{source}|{target}|{relation}".encode("utf-8")).hexdigest()[:10]


def _edge_tags(edge: dict) -> list[str]:
    raw = edge.get("tags") or edge.get("provenance") or []
    if isinstance(raw, str):
        raw = [raw]
    tags = list(raw)
    if edge.get("tag") == "both":
        tags.extend(tag for tag in ("llm", "cooccurrence") if tag not in tags)
    elif edge.get("tag") and edge["tag"] not in tags:
        tags.append(edge["tag"])
    return tags


def _edge_quality(edge: dict, evidence_count: int) -> dict:
    quality = edge.get("quality")
    if not isinstance(quality, dict):
        quality = empty_quality()
    defaults = empty_quality()
    normalized = {**defaults, **quality}
    normalized["evidence_count"] = int(normalized.get("evidence_count") or evidence_count)
    normalized["reasons"] = list(normalized.get("reasons") or [])
    return normalized


def _edge_evidence(edge: dict, tag: str) -> list[dict]:
    raw = edge.get("evidence")
    values = raw if isinstance(raw, list) else ([raw] if raw else [])
    evidence: list[dict] = []
    for value in values:
        if isinstance(value, str):
            text = value.strip()[:300]
            item = {"text": text, "source": tag}
        elif isinstance(value, dict):
            text = str(value.get("text") or value.get("quote") or value.get("snippet") or "").strip()[:300]
            if not text:
                continue
            item = {"text": text, "source": value.get("source") or tag}
            for key in ("chunk_index", "paragraph_index", "sentence_index"):
                if isinstance(value.get(key), int) and value[key] >= 0:
                    item[key] = value[key]
        else:
            continue
        if text and item not in evidence:
            evidence.append(item)
    if not evidence and edge.get("snippet"):
        evidence.append({"text": str(edge["snippet"]).strip()[:300], "source": tag})
    return evidence[:8]


def build_graph(
    doc_id: str,
    doc_name: str,
    entities: list[dict],
    edges: list[dict],
    stats: dict[str, Any] | None = None,
    llm_enabled: bool = False,
    max_nodes: int = 600,
    max_edges: int = 2500,
    created_at: str = "",
) -> dict:
    """Build the final graph: degrees, communities, stable ids, and link metadata."""
    degrees: dict[str, int] = defaultdict(int)
    for edge in edges:
        degrees[edge["source"]] += 1
        degrees[edge["target"]] += 1

    # Keep the most central nodes first (degree, then mentions, then name).
    entities = sorted(
        entities,
        key=lambda n: (-degrees.get(n["key"], 0), -n.get("count", 0), n["name"]),
    )
    kept = entities[:max_nodes]
    kept_keys = {n["key"] for n in kept}
    kept_edges = [
        e for e in edges if e["source"] in kept_keys and e["target"] in kept_keys
    ][:max_edges]

    community = detect_communities(kept, kept_edges)

    nodes: list[dict] = []
    for ent in kept:
        nodes.append(
            {
                "id": node_id(ent["key"]),
                "name": ent["name"],
                "type": ent["type"],
                "snippet": ent.get("snippet", ""),
                "degree": degrees.get(ent["key"], 0),
                "community": community.get(ent["key"], 0),
                "sources": ent.get("sources", []),
                "count": ent.get("count", 1),
            }
        )

    links: list[dict] = []
    directed_edges = 0
    association_edges = 0
    for edge in kept_edges:
        tags = _edge_tags(edge)
        tag = tags[0] if len(tags) == 1 else "both"
        relation_key = edge.get("relation_key") or re.sub(r"[^a-z0-9]+", "_", edge["relation"].lower()).strip("_")
        relation_is_association = relation_key == "associated_with" or edge["relation"].lower() in {
            "co-occurs with",
            "cooccurs with",
            "associated with",
            "related to",
        }
        direction = edge.get("direction")
        if direction not in {"directed", "undirected"}:
            direction = "undirected" if relation_is_association else "directed"
        kind = edge.get("kind")
        if kind not in {"assertion", "association"}:
            kind = "association" if direction == "undirected" else "assertion"
        if kind == "association":
            association_edges += 1
        else:
            directed_edges += 1
        evidence = _edge_evidence(edge, tag)
        original_relation = edge.get("original_relation") or edge["relation"]
        aliases = edge.get("relation_aliases") or [original_relation]
        links.append(
            {
                "id": edge_id(edge["source"], edge["target"], edge["relation"]),
                "source": node_id(edge["source"]),
                "target": node_id(edge["target"]),
                "relation": edge["relation"],
                "relation_key": relation_key,
                "original_relation": original_relation,
                "relation_aliases": list(dict.fromkeys(aliases)),
                "direction": direction,
                "kind": kind,
                "tag": tag,
                "provenance": tags,
                "weight": edge["weight"],
                "snippet": edge.get("snippet", ""),
                "evidence": evidence,
                "quality": _edge_quality(edge, len(evidence)),
            }
        )

    total_stats = {
        **(stats or {}),
        "graph_schema_version": GRAPH_SCHEMA_VERSION,
        "relation_schema_version": RELATION_SCHEMA_VERSION,
        "nodes": len(nodes),
        "edges": len(links),
        "communities": len(set(community.values())),
        "directed_edges": directed_edges,
        "association_edges": association_edges,
    }
    return {
        "document": {
            "id": doc_id,
            "name": doc_name,
            "stats": total_stats,
            "llm_enabled": llm_enabled,
            "created_at": created_at,
            "schema_version": GRAPH_SCHEMA_VERSION,
            "relation_schema_version": RELATION_SCHEMA_VERSION,
        },
        "nodes": nodes,
        "links": links,
    }
