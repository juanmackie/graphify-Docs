"""CSV export: nodes.csv + edges.csv packaged as a zip (spreadsheet-friendly)."""
from __future__ import annotations

import csv
import io
import zipfile
from typing import Any


def _nodes_csv(graph: dict[str, Any]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "name", "type", "degree", "community", "sources", "mentions", "snippet"])
    for n in graph["nodes"]:
        writer.writerow(
            [
                n["id"],
                n["name"],
                n.get("type", ""),
                n.get("degree", 0),
                n.get("community", 0),
                "|".join(n.get("sources", [])),
                n.get("count", 0),
                n.get("snippet", ""),
            ]
        )
    return buf.getvalue().encode("utf-8")


def _edges_csv(graph: dict[str, Any]) -> bytes:
    by_id = {n["id"]: n["name"] for n in graph["nodes"]}
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "source_id",
            "source_name",
            "target_id",
            "target_name",
            "relation",
            "relation_key",
            "original_relation",
            "direction",
            "kind",
            "tag",
            "provenance",
            "weight",
            "quality_score",
            "confidence",
            "support_count",
            "evidence",
            "snippet",
        ]
    )
    for e in graph["links"]:
        quality = e.get("quality") if isinstance(e.get("quality"), dict) else {}
        evidence = e.get("evidence") if isinstance(e.get("evidence"), list) else []
        evidence_text = " || ".join(
            str(item.get("text", "")) for item in evidence if isinstance(item, dict) and item.get("text")
        )
        writer.writerow(
            [
                e["source"],
                by_id.get(e["source"], e["source"]),
                e["target"],
                by_id.get(e["target"], e["target"]),
                e["relation"],
                e.get("relation_key", ""),
                e.get("original_relation", e["relation"]),
                e.get("direction", "directed"),
                e.get("kind", "assertion"),
                e.get("tag", ""),
                "|".join(e.get("provenance", [])),
                e.get("weight", 1),
                quality.get("score", ""),
                quality.get("confidence", ""),
                quality.get("support_count", ""),
                evidence_text,
                e.get("snippet", ""),
            ]
        )
    return buf.getvalue().encode("utf-8")


def render_csv_zip(graph: dict[str, Any]) -> bytes:
    """Return zip bytes containing nodes.csv and edges.csv."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("nodes.csv", _nodes_csv(graph))
        zf.writestr("edges.csv", _edges_csv(graph))
    return buf.getvalue()
