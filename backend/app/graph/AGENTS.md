# Graph AGENTS.md

## Purpose

Build the final `graph.json` (nodes, links, degree, snippets, communities) consumed by the frontend and exports.

## Ownership

- `builder.py` — graph.json construction + stats aggregation
- `schema.py` — versioned relation/evidence/quality contract
- `community.py` — Louvain community detection via python-louvain

## Local Contracts

- **`builder.py`**: emits `{ document: { id, name, stats, llm_enabled, created_at }, nodes, links }`. `stats` spreads the pipeline stats passthrough plus `nodes`, `edges`, `communities` counts. Node = `{ id, name, type, snippet, degree, community, sources, count }`; legacy links retain `{ id, source, target, relation, tag, weight, snippet }` and version 2 links add `relation_key`, `original_relation`, `relation_aliases`, `direction`, `kind`, `provenance`, `evidence`, and `quality`. Applies `max_nodes` / `max_edges` caps.
- **`schema.py`**: version 2 graph contract, version 1 relation contract, evidence/quality field definitions, and valid direction/kind/provenance values. New fields must be additive so old graph consumers remain valid.
- **`community.py`**: weighted node graph via `community.best_partition`; community ids stored per node. Pinned `networkx>=3.0,<3.5` + `python-louvain==0.16` — do not bump independently.

## Work Guidance

- Node/edge ids must be stable strings (used by path queries and the React force graph); never emit raw indices.
- Preserve `sources` (`llm`/`yake`) and `tag` — filtering and exports depend on them.
- If community detection must ever be replaced (e.g. `igraph`+`leidenalg`), keep the same stats shape (`communities` count).

## Verification

- `pytest tests/test_graph.py` — schema validity, degree/community/stats presence.
- Manual: open a generated graph in the frontend and confirm community coloring + node panel.

## Child DOX Index

- No child AGENTS.md files.
