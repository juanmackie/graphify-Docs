"""Readable Markdown report export (the "GRAPH_REPORT" analogue)."""
from __future__ import annotations

from collections import Counter
from typing import Any


def render_markdown_report(graph: dict[str, Any]) -> str:
    doc = graph["document"]
    nodes: list[dict] = graph["nodes"]
    links: list[dict] = graph["links"]
    stats: dict[str, Any] = doc.get("stats", {})

    by_id = {n["id"]: n for n in nodes}
    name_of = lambda node_id: by_id.get(node_id, {}).get("name", node_id)

    lines: list[str] = []
    lines.append(f"# {doc.get('name', 'Document')} — Knowledge Graph Report")
    lines.append("")
    lines.append(f"*Generated from the DocGraph pipeline.*")
    lines.append("")

    # Overview
    lines.append("## Overview")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Nodes | {stats.get('nodes', len(nodes))} |")
    lines.append(f"| Edges | {stats.get('edges', len(links))} |")
    lines.append(f"| Communities | {stats.get('communities', 0)} |")
    lines.append(f"| Text chunks analyzed | {stats.get('chunks', 0)} |")
    lines.append(f"| LLM-extracted edges | {stats.get('llm_edges', 0)} |")
    lines.append(f"| Co-occurrence edges | {stats.get('cooc_edges', 0)} |")
    lines.append(f"| Extraction mode | {'LLM + statistical' if doc.get('llm_enabled') else 'statistical only'} |")
    lines.append(f"| Graph schema | v{doc.get('schema_version', stats.get('graph_schema_version', 1))} |")
    lines.append(f"| Directed assertions | {stats.get('directed_edges', 0)} |")
    lines.append(f"| Undirected associations | {stats.get('association_edges', 0)} |")
    lines.append("")

    # God nodes
    top_nodes = sorted(nodes, key=lambda n: (-n.get("degree", 0), n["name"]))[:10]
    lines.append("## Most-connected concepts (god nodes)")
    lines.append("")
    lines.append("| Concept | Type | Degree | Mentions |")
    lines.append("|---|---|---|---|")
    for n in top_nodes:
        lines.append(f"| {n['name']} | {n.get('type', '')} | {n.get('degree', 0)} | {n.get('count', 0)} |")
    lines.append("")

    # Communities
    communities: dict[int, list[dict]] = {}
    for n in nodes:
        communities.setdefault(n.get("community", 0), []).append(n)
    lines.append("## Communities")
    lines.append("")
    for cid in sorted(communities):
        members = sorted(communities[cid], key=lambda n: -n.get("degree", 0))
        top = ", ".join(f"**{m['name']}**" for m in members[:8])
        more = f" (+{len(members) - 8} more)" if len(members) > 8 else ""
        lines.append(f"### Community {cid} — {len(members)} nodes")
        lines.append("")
        lines.append(f"{top}{more}")
        lines.append("")

    # Key relationships
    top_edges = sorted(links, key=lambda l: (-l.get("weight", 1), l["relation"]))[:25]
    lines.append("## Key relationships")
    lines.append("")
    lines.append("| Source | Relation | Target | Semantics | Provenance | Weight | Confidence | Evidence |")
    lines.append("|---|---|---|---|---|---:|---:|---|")
    for e in top_edges:
        quality = e.get("quality") if isinstance(e.get("quality"), dict) else {}
        evidence = e.get("evidence") if isinstance(e.get("evidence"), list) else []
        evidence_text = next(
            (str(item.get("text", "")) for item in evidence if isinstance(item, dict) and item.get("text")),
            e.get("snippet", ""),
        )
        confidence = quality.get("confidence")
        confidence_text = f"{float(confidence) * 100:.0f}%" if isinstance(confidence, (int, float)) else "—"
        provenance = " + ".join(e.get("provenance", [])) or e.get("tag", "")
        semantics = "↔ association" if e.get("direction") == "undirected" else "→ assertion"
        lines.append(
            f"| {name_of(e['source'])} | {e['relation']} | {name_of(e['target'])} "
            f"| {semantics} | {provenance} | {e.get('weight', 1)} | {confidence_text} | {evidence_text} |"
        )
    lines.append("")

    # Relation distribution
    rel_counts = Counter(e["relation"] for e in links)
    lines.append("## Relationship types")
    lines.append("")
    lines.append("| Relation | Count |")
    lines.append("|---|---|")
    for rel, count in rel_counts.most_common(15):
        lines.append(f"| {rel} | {count} |")
    lines.append("")

    # Method note
    lines.append("## Method")
    lines.append("")
    if doc.get("llm_enabled"):
        lines.append(
            "Entities and typed relationships were extracted by an LLM over overlapping "
            "text chunks, then merged and deduplicated. A statistical pass (YAKE keyword "
            "ranking + co-occurrence) supplements the graph. Communities were detected "
            "with the Louvain algorithm."
        )
    else:
        lines.append(
            "No LLM API key was configured, so this graph was built from the statistical "
            "pass only: YAKE keyword ranking plus deterministic sentence/paragraph/window "
            "association candidates. Configure an OpenAI-compatible API key and re-upload "
            "for richer, typed relationships."
        )
    lines.append("")
    lines.append(
        "Relation evidence, provenance, direction, and confidence are preserved in the "
        "graph. User correction overlays are intentionally deferred; future rejected edges "
        "will be hidden from the effective graph without deleting raw extraction."
    )
    lines.append("")

    # Suggested questions
    lines.append("## Questions this graph can help answer")
    lines.append("")
    lines.append("- Which concepts are the most central to this document? (see god nodes)")
    lines.append("- What are the main thematic clusters? (see communities)")
    lines.append("- How do two given concepts connect? (use the path query in the interactive view)")
    lines.append("- Which relationships appear most frequently? (see relationship types)")
    lines.append("")

    return "\n".join(lines)
