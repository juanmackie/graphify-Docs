# Code Context

## Files Retrieved
1. `backend/app/extraction/llm.py` (lines 22-50, 142-193) - extraction prompt and response limits/normalization.
2. `backend/app/extraction/statistical.py` (lines 35-101, 120-260, 261-330) - YAKE candidate generation and deterministic association linking.
3. `backend/app/extraction/merge.py` (lines 22-108, 228-370) - canonicalization, edge merging, endpoint materialization.
4. `backend/app/pipeline.py` (lines 35-105) - sequencing and combined inputs.
5. `backend/app/ingestion/chunker.py` (lines 25-74) - overlapping chunk construction.
6. `backend/app/graph/builder.py` (lines 41-150) - degree-based node retention and final links.

## Key Code

### High severity: statistical pass turns broad lexical salience into semantic edges
`statistical.extract_statistical` always runs and feeds YAKE keywords plus every LLM entity into `document_link_candidates`. YAKE emits up to 40 phrases (`statistical.py:35-73`), with only length/numeric filtering; no stop-list, domain vocabulary, section/header/table filtering, or noun/entity validation. `_in_text` accepts any matching phrase (`:75-90`).

`document_link_candidates` creates pairs for every candidate co-mentioned in a sentence, two-sentence window, or compact paragraph, scoring `3*sentence + 2*window + paragraph` and retaining score >=2 (`statistical.py:120-260`). Thus a long AS 1851 requirement/procedure sentence can produce many plausible-looking but non-relational edges (e.g. equipment, interval, responsible party, records, “must”, references). Two adjacent sentences are enough for an association even when no assertion connects the concepts. Low-risk fix: preserve this pass but expose/filter it separately by default; require direct same-sentence support (or higher repeated support) for displayed edges, and explicitly suppress generic requirement/control vocabulary and numeric/time-only phrases. Make thresholds/config measurable rather than deleting statistical capability.

### High severity: graph combines *all* keyword nodes with co-occurrence links
`merge_all` appends all YAKE keywords as `type="keyword"` nodes, then adds LLM endpoints and statistical edges (`merge.py:320-370`). There is no quality cutoff before graph build. A document with 40 noisy keywords can therefore have a large semantic-looking graph even when LLM extraction is good. Low-risk fix: retain raw keywords in meta, but only promote candidates with repeated mentions/domain allowlist or meaningful LLM support; or render keyword-only nodes/edges as an optional inferred layer.

### High severity: LLM is instructed to over-extract on every chunk and overlap duplicates evidence
The system prompt asks for 5-25 entities and 5-30 relations *per chunk* (`llm.py:22-50`), which encourages filler relations in standards prose. It also permits relation endpoints not in the entity list (`:44-46`). Parser truncates/accepts up to 30 entities and 40 relations (`:142-193`), so the prompt's minimum is not a safety guard. Chunks overlap by up to 200 characters (`chunker.py:35-74`), and `extract_document` concatenates all per-chunk entities/relations (`llm.py:424-508`) before merge. Name deduplication reduces duplicate nodes but not semantically repeated/contradictory assertions. Low-risk fix: change prompt to “only extract if evidence is explicit; zero allowed,” lower a per-chunk relation cap, and deduplicate/score relation evidence by normalized quote/chunk before graph display. Consider overlap only for boundary context, not repeated relation support.

### Medium severity: normalization collapses distinct standard terms and preserves ambiguous phrases
`normalize_name` lowercases, strips punctuation, and removes leading articles (`merge.py:65-72`). This merges spelling/casing variants safely in many cases, but no acronym, singular/plural, unit, clause, or parenthetical handling exists. Conversely, distinct phrases (“inspection”, “inspection records”, “inspection frequency”) remain separate nodes. Relation labels outside the small alias map become arbitrary custom keys (`merge.py:74-102`), allowing near-synonymous LLM verbs to remain separate edges. Low-risk fix: add only audited AS 1851 alias mappings (and explicit acronym rules), never fuzzy-merge without evidence; map generic relation labels to a single low-confidence association or reject them.

### Medium severity: relation endpoints are deliberately materialized even when unsupported as entities
`merge_all` adds missing relation endpoints as minimal concept nodes (`merge.py:337-357`). This prevents capability loss but can make model hallucinations visible as first-class nodes. Quality records weaker support, but `build_graph` does not filter by quality (`builder.py:41-71`). Low-risk fix: keep raw/materialized endpoints in metadata, but require endpoint support or explicit evidence validation for the effective graph; report rejected edges rather than silently dropping them.

### Medium severity: node/edge caps amplify central lexical hubs rather than semantic quality
`build_graph` ranks nodes by degree first, then mention count, then name and keeps first 600; edges are sliced to 2500 (`builder.py:55-71`). Co-occurrence hubs (common terms such as maintenance, system, record) gain degree from many weak associations and crowd out specific entities. Low-risk fix: rank/trim using edge quality and provenance-weighted degree, and retain a representative per community/relation; apply quality filtering before degree calculation.

### Pipeline/data-flow
`pipeline.py:35-105` parses, chunks, samples chunks for LLM, runs statistical extraction over the complete document, merges both streams, then builds graph. This means fast/balanced LLM selection does not reduce statistical noise: all full-document text still contributes YAKE and locality links. `llm_enabled=False` still produces the entire statistical graph (`llm.py:416-419`, pipeline calls statistical unconditionally).

## AS 1851 report availability
No AS 1851 report file or generated graph/report was present in the repository tree (only source code and screenshots). Therefore report-specific node examples, counts, and exact noisy edge samples could not be attested. The findings above are code-backed causes expected to be especially visible in standards documents (dense tables, clause references, repeated “shall/must” procedural language), but should be validated against the report's `graph.json`/`meta.json` counts and evidence snippets before tuning thresholds.

## Architecture
Parser -> paragraph-aware overlapping chunks -> optional LLM extraction on selected chunks + always-on full-document YAKE/locality extraction -> merge/dedup/canonical relation handling -> graph builder quality metadata, degree ranking, community detection, and caps. Statistical associations and LLM assertions share the final `links` collection; frontend receives both unless it filters by tag.

## Start Here
Open `backend/app/pipeline.py` first to confirm the dual-stream data flow, then `backend/app/extraction/statistical.py` and `backend/app/extraction/llm.py` for the two independent noise sources. Use evidence snippets in the report graph to distinguish lexical co-occurrence noise from LLM assertions.

```acceptance-report
{
  "criteriaSatisfied": [
    {"id": "criterion-1", "status": "satisfied", "evidence": "Concrete severity-ranked findings cite backend extraction, merge, pipeline, chunking, and graph-builder paths with low-risk fixes."}
  ],
  "changedFiles": [],
  "testsAddedOrUpdated": [],
  "commandsRun": [],
  "validationOutput": ["Repository inspection completed; no source files modified."],
  "residualRisks": ["AS 1851 report/graph artifact was not present in the repository, so report-specific examples and measured noise rates remain unverified.", "Threshold changes require evaluation on the actual report to avoid suppressing legitimate standard relationships."],
  "noStagedFiles": true,
  "diffSummary": "No files changed; findings written as requested.",
  "reviewFindings": ["high: backend/app/extraction/statistical.py:120-260 - broad sentence/window/paragraph co-occurrence emits associations without semantic relation evidence.", "high: backend/app/extraction/llm.py:22-50 - per-chunk minimum extraction quotas encourage filler entities/relations; overlap duplicates extraction.", "high: backend/app/extraction/merge.py:320-370 - all YAKE keywords become graph nodes and all statistical edges are retained.", "medium: backend/app/graph/builder.py:55-71 - degree-first caps favor weak lexical hubs.", "medium: backend/app/extraction/merge.py:337-357 - unsupported relation endpoints are materialized as nodes."],
  "manualNotes": "No AS 1851 report artifact was discoverable under the repository; correlate these mechanisms with the report's graph evidence before tuning."
}
```