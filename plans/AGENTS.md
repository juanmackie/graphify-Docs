# Plans AGENTS.md

## Purpose

Working plan files for feature work. A plan is a single Markdown document that captures context, approach, files to modify, steps, and verification before implementation starts.

## Ownership

- `stage-timings.md` — the current/latest feature plan (pipeline stage timings in the UI)
- Future plans: one file per feature, named by area, e.g. `plans/<short-name>.md`

## Local Contracts

- Plan shape: **Context** (with measured evidence when performance-related), **Approach**, **Files to modify**, **Reuse**, **Steps** (checkbox list), **Verification** (concrete commands + what "done" looks like).
- Performance plans must lead with measurements (e.g. "parse = 2.1s, LLM stage dominates") — never optimize blind.
- Plans are written before code and revised as implementation reveals facts.

## Work Guidance

- A plan is a work contract, not a diary: keep it current, check off steps, and correct the record if the implementation diverges.
- When a plan is approved and executed, leave it in place (version history for future similar work).

## Verification

- Plan file exists, steps reflect the final implementation, and verification commands actually ran green.

## Child DOX Index

- No child AGENTS.md files.
