# Docs AGENTS.md

## Purpose

Project documentation assets: pipeline diagram and UI screenshots used by `README.md`.

## Ownership

- `pipeline.svg` — end-to-end architecture diagram (mirrors the README "Pipeline" section)
- `shot-*.png` / `screenshot-export-html.png` — UI screenshots

## Local Contracts

- `pipeline.svg` must stay consistent with the README architecture description (parse → chunk → LLM + statistical → merge → graph → exports).
- Screenshots should reflect the current UI; update them when a visible component changes meaningfully.

## Work Guidance

- Keep binary assets small and committed; prefer SVGs over raster for diagrams.
- When README describes a new stage/feature, update `pipeline.svg` in the same change.

## Verification

- Visual: open `pipeline.svg` and screenshots; confirm they match the current UI and README text.
- No automated checks in this scope.

## Child DOX Index

- No child AGENTS.md files.
