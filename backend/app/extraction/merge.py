"""Normalize, validate, and merge raw extractions into graph entities/edges."""
from __future__ import annotations

import re
from typing import Any

_ARTICLE_RE = re.compile(r"^(the|a|an)\s+")
_WS_RE = re.compile(r"\s+")
_TRIM_PUNCT = ".,;:!?()[]{}'\"“”‘’*•-"
_ENTITY_NOISE_PHRASES = (
    "accessed by ",
    "document currency",
    "standards australia www",
    "records result",
    "item action",
    "requirement records",
    "service records records",
)
_ENTITY_NOISE_WORDS = {"accessed", "currency", "printed", "comments", "pass/fail"}
_ENTITY_DESCRIPTOR_WORDS = {"correct", "satisfactory", "fitted", "competent", "fully", "latch"}

# Canonical relation keys are intentionally small for useful filtering. Unknown
# labels remain valid custom keys, so extraction never loses a meaningful edge.
# The boolean marks aliases whose natural subject/object order is reversed.
_RELATION_ALIASES: dict[str, tuple[str, bool]] = {
    "is a": ("is_a", False),
    "is an": ("is_a", False),
    "is a type of": ("is_a", False),
    "is type of": ("is_a", False),
    "is-a-type-of": ("is_a", False),
    "type of": ("is_a", False),
    "kind of": ("is_a", False),
    "part of": ("part_of", False),
    "is part of": ("part_of", False),
    "belongs to": ("part_of", False),
    "contained in": ("part_of", False),
    "contains": ("contains", False),
    "includes": ("contains", False),
    "has": ("contains", False),
    "depends on": ("depends_on", False),
    "dependent on": ("depends_on", False),
    "relies on": ("depends_on", False),
    "requires": ("depends_on", False),
    "is used by": ("uses", True),
    "used by": ("uses", True),
    "uses": ("uses", False),
    "utilizes": ("uses", False),
    "employs": ("uses", False),
    "causes": ("causes", False),
    "leads to": ("causes", False),
    "results in": ("causes", False),
    "mentions": ("mentions", False),
    "refers to": ("mentions", False),
    "discusses": ("mentions", False),
    "co-occurs with": ("associated_with", False),
    "cooccurs with": ("associated_with", False),
    "co occurs with": ("associated_with", False),
    "associated with": ("associated_with", False),
    "related to": ("associated_with", False),
}
_RELATION_LABELS = {
    "is_a": "is a",
    "part_of": "part of",
    "contains": "contains",
    "depends_on": "depends on",
    "uses": "uses",
    "causes": "causes",
    "mentions": "mentions",
    # Keep the existing UI/export label while exposing a stable relation_key.
    "associated_with": "co-occurs with",
}


def normalize_name(name: str) -> str:
    """Canonical key for an entity: lowercase, single spaces, no leading article."""
    name = (name or "").replace("�", "-")
    name = _WS_RE.sub(" ", name.strip().lower())
    name = name.strip(_TRIM_PUNCT)
    name = _ARTICLE_RE.sub("", name).strip()
    return name


def is_usable_entity_name(name: str) -> bool:
    """Reject OCR/table fragments that cannot teach a concept."""
    normalized = normalize_name(name)
    if not normalized or len(normalized) < 2:
        return False
    if any(phrase in normalized for phrase in _ENTITY_NOISE_PHRASES):
        return False
    words = normalized.split()
    if len(words) > 6 or "�" in normalized:
        return False
    if len(words) >= 5 and any(word in _ENTITY_DESCRIPTOR_WORDS for word in words):
        return False
    if words[0] in {"item", "records", "requirement", "accessed", "this"} and len(words) > 1:
        return False
    if len(words) >= 3 and sum(word in _ENTITY_NOISE_WORDS for word in words) >= 2:
        return False
    return bool(re.search(r"[a-z]", normalized))


def normalize_relation(relation: str) -> str:
    rel = _WS_RE.sub(" ", (relation or "").strip().lower())
    return rel.strip(_TRIM_PUNCT)


def canonicalize_relation(relation: str) -> dict[str, Any] | None:
    """Return a stable relation key/label and whether endpoints must swap."""
    normalized = normalize_relation(relation)
    if not normalized or not re.search(r"[a-z0-9]", normalized):
        return None
    token = _WS_RE.sub(" ", normalized.replace("_", " ").replace("/", " ")).strip()
    alias = _RELATION_ALIASES.get(token)
    if alias is None:
        relation_key = re.sub(r"[^a-z0-9]+", "_", token).strip("_")
        display = normalized
        swap = False
    else:
        relation_key, swap = alias
        display = _RELATION_LABELS.get(relation_key, normalized)
    if not relation_key:
        return None
    return {
        "relation": display,
        "relation_key": relation_key,
        "original_relation": (relation or "").strip()[:120] or display,
        "swap": swap,
    }


def _most_common(counter: dict[str, int]) -> str:
    return max(counter, key=counter.get)


def merge_entities(raw_entities: list[dict]) -> list[dict]:
    """Deduplicate raw entity dicts by normalized name.

    Raw entity: {"name", "type", "snippet", "source"}. Relation endpoints
    materialized by :func:`merge_all` are ordinary concept nodes, which keeps a
    useful edge instead of silently dropping a model relation.
    """
    merged: dict[str, dict] = {}
    for ent in raw_entities:
        norm = normalize_name(ent.get("name", ""))
        if not norm:
            continue
        node = merged.get(norm)
        if node is None:
            node = merged[norm] = {
                "key": norm,
                "name": ent.get("name", ""),
                "type": ent.get("type", "concept"),
                "snippet": ent.get("snippet", "") or "",
                "sources": [],
                "count": 0,
                "_names": {},
                "_types": {},
            }
        spelling = (ent.get("name") or "").strip() or norm
        node["_names"][spelling] = node["_names"].get(spelling, 0) + 1
        entity_type = ent.get("type") or "concept"
        node["_types"][entity_type] = node["_types"].get(entity_type, 0) + 1
        node["count"] += 1
        if not node["snippet"] and ent.get("snippet"):
            node["snippet"] = ent["snippet"]
        src = ent.get("source", "llm")
        if src not in node["sources"]:
            node["sources"].append(src)

    result: list[dict] = []
    for node in merged.values():
        node["name"] = _most_common(node["_names"])
        node["type"] = _most_common(node["_types"])
        node.pop("_names", None)
        node.pop("_types", None)
        result.append(node)
    result.sort(key=lambda n: (-n["count"], n["name"]))
    return result


def _tag_list(edge: dict) -> list[str]:
    values: list[str] = []
    raw_values = edge.get("tags") or edge.get("provenance") or []
    if isinstance(raw_values, str):
        raw_values = [raw_values]
    for value in [*raw_values, edge.get("tag")]:
        if value == "both":
            candidates = ["llm", "cooccurrence"]
        elif isinstance(value, str):
            candidates = [value]
        else:
            candidates = []
        for candidate in candidates:
            if candidate and candidate not in values:
                values.append(candidate)
    return values or ["llm"]


def _evidence_items(edge: dict, tags: list[str]) -> list[dict]:
    raw = edge.get("evidence")
    values = raw if isinstance(raw, list) else ([raw] if raw else [])
    if not values and edge.get("snippet"):
        values = [{"text": edge.get("snippet")}]
    output: list[dict] = []
    default_source = "cooccurrence" if "cooccurrence" in tags and "llm" not in tags else "llm"
    for value in values:
        if isinstance(value, str):
            text = value.strip()[:300]
            metadata: dict = {}
        elif isinstance(value, dict):
            text = str(value.get("text") or value.get("quote") or value.get("snippet") or "").strip()[:300]
            metadata = value
        else:
            continue
        if not text:
            continue
        item: dict[str, Any] = {"text": text, "source": metadata.get("source") or default_source}
        for output_key, input_keys in (
            ("chunk_index", ("chunk_index", "chunk")),
            ("paragraph_index", ("paragraph_index", "paragraph")),
            ("sentence_index", ("sentence_index", "sentence")),
        ):
            for input_key in input_keys:
                value = metadata.get(input_key)
                if isinstance(value, int) and value >= 0:
                    item[output_key] = value
                    break
        if item not in output:
            output.append(item)
        if len(output) >= 8:
            break
    return output


def _quality(
    tags: list[str],
    support_count: int,
    evidence_count: int,
    endpoint_support: float,
    weight: int,
) -> dict[str, Any]:
    source_score = 1.0 if "manual" in tags else 0.9 if "llm" in tags and "cooccurrence" not in tags else 0.78 if "llm" in tags else 0.62
    support_score = min(1.0, max(support_count, weight) / 3.0)
    evidence_score = min(1.0, evidence_count / 3.0)
    score = round(0.35 * source_score + 0.25 * support_score + 0.2 * evidence_score + 0.2 * endpoint_support, 3)
    confidence = round(0.45 * score + 0.3 * endpoint_support + 0.25 * support_score, 3)
    reasons: list[str] = []
    if "llm" in tags:
        reasons.append("typed extraction")
    if "cooccurrence" in tags:
        reasons.append("document locality")
    if support_count > 1:
        reasons.append("repeated support")
    if evidence_count > 1:
        reasons.append("multiple evidence")
    if endpoint_support < 1:
        reasons.append("endpoint materialized from relation")
    return {
        "score": score,
        "confidence": confidence,
        "support_count": support_count,
        "endpoint_support": round(endpoint_support, 3),
        "evidence_count": evidence_count,
        "reasons": reasons,
    }


def merge_edges(raw_edges: list[dict], known_entity_keys: set[str] | None = None) -> list[dict]:
    """Merge equivalent directed/inferred edges with evidence and quality."""
    merged: dict[tuple[str, str, str, str], dict] = {}
    known = known_entity_keys
    for edge in raw_edges:
        src = normalize_name(edge.get("source", ""))
        tgt = normalize_name(edge.get("target", ""))
        canonical = canonicalize_relation(edge.get("relation", ""))
        if canonical is not None and edge.get("original_relation"):
            canonical["original_relation"] = str(edge.get("original_relation"))[:120]
        if not src or not tgt or src == tgt or canonical is None:
            continue

        tags = _tag_list(edge)
        direction = str(edge.get("direction") or "").lower()
        kind = str(edge.get("kind") or "").lower()
        inferred_association = (
            canonical["relation_key"] == "associated_with"
            or direction == "undirected"
            or kind == "association"
        )
        if direction not in {"directed", "undirected"}:
            direction = "undirected" if inferred_association else "directed"
        if kind not in {"assertion", "association"}:
            kind = "association" if direction == "undirected" else "assertion"
        if direction == "undirected":
            kind = "association"
        if canonical["swap"] and direction == "directed":
            src, tgt = tgt, src

        if direction == "undirected" and tgt < src:
            src, tgt = tgt, src
        key = (src, tgt, canonical["relation_key"], direction)
        item = merged.get(key)
        if item is None:
            item = merged[key] = {
                "source": src,
                "target": tgt,
                "relation": canonical["relation"],
                "relation_key": canonical["relation_key"],
                "original_relation": canonical["original_relation"],
                "relation_aliases": [canonical["original_relation"]],
                "direction": direction,
                "kind": kind,
                "weight": 0,
                "tags": [],
                "provenance": [],
                "support_count": 0,
                "evidence": [],
                "_endpoint_support": [],
            }
        item["weight"] += max(1, int(edge.get("weight", 1) or 1))
        item["support_count"] += max(1, int(edge.get("support_count", 1) or 1))
        for tag in tags:
            if tag not in item["tags"]:
                item["tags"].append(tag)
            if tag not in item["provenance"]:
                item["provenance"].append(tag)
        original = canonical["original_relation"]
        if original not in item["relation_aliases"]:
            item["relation_aliases"].append(original)
        evidence = _evidence_items(edge, tags)
        for evidence_item in evidence:
            if evidence_item not in item["evidence"] and len(item["evidence"]) < 8:
                item["evidence"].append(evidence_item)
        if known is None:
            endpoint_support = 1.0
        else:
            endpoint_support = sum(endpoint in known for endpoint in (src, tgt)) / 2.0
        item["_endpoint_support"].append(endpoint_support)

    result: list[dict] = []
    for item in merged.values():
        evidence = item.pop("evidence")
        endpoint_supports = item.pop("_endpoint_support")
        item["snippet"] = evidence[0]["text"] if evidence else ""
        item["quality"] = _quality(
            item["tags"],
            item.pop("support_count"),
            len(evidence),
            sum(endpoint_supports) / len(endpoint_supports) if endpoint_supports else 1.0,
            item["weight"],
        )
        result.append(item | {"evidence": evidence})
    return sorted(result, key=lambda edge: (-edge["weight"], edge["source"], edge["target"], edge["relation_key"]))


def merge_all(
    llm_entities: list[dict] | None = None,
    llm_relations: list[dict] | None = None,
    keywords: list[dict] | None = None,
    cooccurrence_edges: list[dict] | None = None,
) -> dict:
    """Combine LLM + statistical output, retaining every valid relation endpoint."""
    raw_entities: list[dict] = []
    for ent in llm_entities or []:
        if is_usable_entity_name(str(ent.get("name", ""))):
            raw_entities.append({**ent, "source": "llm"})
    for kw in keywords or []:
        if is_usable_entity_name(str(kw.get("name", ""))):
            raw_entities.append(
                {
                    "name": kw.get("name", ""),
                    "type": "keyword",
                    "snippet": "",
                    "source": "yake",
                }
            )

    raw_edges: list[dict] = []
    for rel in llm_relations or []:
        if is_usable_entity_name(str(rel.get("source", ""))) and is_usable_entity_name(str(rel.get("target", ""))):
            raw_edges.append({**rel, "tag": "llm", "weight": 1, "_origin": "llm"})
    for edge in cooccurrence_edges or []:
        if is_usable_entity_name(str(edge.get("source", ""))) and is_usable_entity_name(str(edge.get("target", ""))):
            raw_edges.append({**edge, "relation": edge.get("relation", "co-occurs with"), "tag": "cooccurrence", "_origin": "cooccurrence"})

    original_entity_keys = {normalize_name(entity.get("name", "")) for entity in raw_entities}
    known_before_relations = set(original_entity_keys)
    # LLMs occasionally return a relation endpoint without repeating it in the
    # entity list. Materialize it as a minimal concept node instead of dropping
    # the relation; the quality score records the weaker endpoint support.
    for edge in raw_edges:
        for endpoint in (edge.get("source", ""), edge.get("target", "")):
            key = normalize_name(endpoint)
            if key and key not in known_before_relations:
                raw_entities.append(
                    {
                        "name": endpoint,
                        "type": "concept",
                        "snippet": edge.get("snippet", "") or "",
                        "source": edge.get("_origin", "llm"),
                    }
                )
                known_before_relations.add(key)

    entities = merge_entities(raw_entities)
    edges = merge_edges(raw_edges, known_entity_keys=original_entity_keys)
    return {"entities": entities, "edges": edges}
