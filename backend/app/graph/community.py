"""Community detection (Louvain) via networkx + python-louvain."""
from __future__ import annotations

import networkx as nx
from community import community_louvain


def detect_communities(
    entities: list[dict],
    edges: list[dict],
    resolution: float = 1.0,
) -> dict[str, int]:
    """Map node key -> community id. Isolated nodes each get their own community."""
    graph = nx.Graph()
    graph.add_nodes_from(e["key"] for e in entities)
    graph.add_weighted_edges_from((e["source"], e["target"], e["weight"]) for e in edges)

    if graph.number_of_nodes() == 0:
        return {}
    if graph.number_of_edges() == 0:
        return {node: i for i, node in enumerate(sorted(graph.nodes))}

    partition = community_louvain.best_partition(
        graph, weight="weight", resolution=resolution, random_state=42
    )
    # Remap community ids so the largest community is 0 (stable coloring)
    by_size = sorted(set(partition.values()), key=lambda c: -sum(1 for v in partition.values() if v == c))
    remap = {old: new for new, old in enumerate(by_size)}
    return {node: remap[c] for node, c in partition.items()}
