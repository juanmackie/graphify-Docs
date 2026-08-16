# Export AGENTS.md

## Purpose

Three download formats from a finished graph: self-contained interactive HTML, a readable Markdown report, and CSV spreadsheets.

## Ownership

- `html.py` — self-contained `graph.html`
- `report.py` — Markdown report (god nodes, communities, key relationships, stats)
- `csv.py` — `nodes.csv` + `edges.csv` (zip)

## Local Contracts

- **`html.py`**: single-file interactive graph; the `force-graph` library loads from a CDN (`https://unpkg.com/force-graph@1`), so the file needs internet to render. Everything else is inlined. Hostable anywhere (GitHub Pages, Netlify, S3). The initial canvas shows the strongest connected component, with selected-component and all-visible views, component navigation, seeded layout, community spacing, curved parallel links, bounded small-component zoom, and container-sized responsive canvas. Deep-dive focus keeps unrelated nodes and links moderately visible for navigation. Link tooltips/panels and filters mirror the frontend's direction, provenance, semantic kind, confidence, and evidence inspection.
- **`report.py`**: human-readable Markdown; mirrors the frontend's god-node/community summaries and includes relation semantics, provenance, confidence, and evidence.
- **`csv.py`**: spreadsheet-friendly rows; zip containing both CSVs, including stable relation key, direction/kind, provenance, quality, and evidence columns.
- All three read the same `graph.json` via the shared graph schema (see `graph/AGENTS.md`) — never parse `meta.json` as the source of truth for exports.

## Work Guidance

- Keep the HTML export's interaction parity with the frontend (core/selected/all map scopes, search, click, filter, path, fit/reset controls) when the app UI changes.
- Exports must work offline for the *content* (only the CDN library needs internet).

## Verification

- `pytest tests/test_export.py` — HTML contains expected structure, report renders, CSV zip has both files.
- Manual: download each export and open in browser / spreadsheet app.

## Child DOX Index

- No child AGENTS.md files.
