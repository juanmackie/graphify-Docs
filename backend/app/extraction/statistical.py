"""Statistical extraction: YAKE ranking plus deterministic document linking.

This pass runs with zero API cost and backs up LLM extraction. Keywords become
candidate entity nodes, while sentence/paragraph/window locality and repeated
support produce explicit undirected association edges. These edges are the
"INFERRED" analogue to LLM "EXTRACTED" relations, never directed assertions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import yake

from .merge import is_usable_entity_name

_NOISE_LINE_RE = re.compile(
    r"^(?:item|no\.?|records?|result|pass/fail|comments?|accessed by|document currency)",
    re.IGNORECASE,
)
_KEYWORD_NOISE_WORDS = {
    "action", "appendix", "australia", "check", "comments", "complete", "fail",
    "item", "pass", "records", "required", "result", "schedule", "section",
    "service", "standards", "system",
}

_WORD_BOUNDARY = re.compile(r"\b")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


@dataclass
class Keyword:
    name: str
    score: float = 0.0  # yake score — lower is better
    count: int = 0
    source: str = "yake"


def normalize_keyword(phrase: str) -> str:
    """Lowercase, collapse whitespace, trim stray punctuation."""
    name = re.sub(r"\s+", " ", phrase).strip().lower().replace("�", "-")
    name = name.strip(".,;:!?()[]{}'\"“”‘’")
    return name


def _in_text(keyword: str, lower_text: str) -> bool:
    """Word-boundary match for single words, substring for multi-word phrases."""
    if " " not in keyword:
        return _WORD_BOUNDARY.search(lower_text, 0) is not None and bool(
            re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", lower_text)
        )
    return keyword in lower_text


def _count_in_text(keyword: str, lower_text: str) -> int:
    if " " not in keyword:
        return len(re.findall(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", lower_text))
    return lower_text.count(keyword)


def extract_keywords(
    text: str,
    max_keywords: int = 40,
    language: str = "en",
) -> list[Keyword]:
    """Rank the most salient phrases in *text* using YAKE."""
    if not text or not text.strip():
        return []
    extractor = yake.KeywordExtractor(
        lan=language,
        n=3,
        dedupLim=0.9,
        dedupFunc="seqm",
        windowsSize=1,
        top=max_keywords * 2,
    )
    lower = text.lower()
    keywords: list[Keyword] = []
    seen: set[str] = set()
    for phrase, score in extractor.extract_keywords(text):
        name = normalize_keyword(phrase)
        if not name or name in seen:
            continue
        if len(name) < 3 or len(name.split()) > 6 or not is_usable_entity_name(name):
            continue
        words = set(name.split())
        if len(words) == 1 and next(iter(words)) in _KEYWORD_NOISE_WORDS:
            continue
        if words & {"action", "check", "comments", "complete", "fail", "pass", "required", "result"}:
            continue
        if "schedule" in words and "service" not in words and "routine" not in words:
            continue
        if len(words) >= 2 and len(words & _KEYWORD_NOISE_WORDS) >= 2:
            continue
        if re.fullmatch(r"[0-9\W]+", name):
            continue
        seen.add(name)
        keywords.append(Keyword(name=name, score=score, count=_count_in_text(name, lower)))
        if len(keywords) >= max_keywords:
            break
    return keywords


def cooccurrence_edges(
    chunks: list[str],
    keywords: list[Keyword],
    min_weight: int = 2,
) -> list[dict]:
    """Weighted undirected edges between keywords co-occurring in a chunk.

    Returns: [{"source": kw, "target": kw, "weight": n}, ...] with weight = number
    of chunks where both keywords appear (filtered by min_weight).
    """
    if not chunks or not keywords:
        return []
    counter: dict[tuple[str, str], int] = {}
    for chunk in chunks:
        lower = chunk.lower()
        present = [k.name for k in keywords if _in_text(k.name, lower)]
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                a, b = present[i], present[j]
                key = (a, b) if a < b else (b, a)
                counter[key] = counter.get(key, 0) + 1
    return [
        {"source": a, "target": b, "weight": w}
        for (a, b), w in sorted(counter.items(), key=lambda kv: -kv[1])
        if w >= min_weight
    ]


def _paragraphs_and_sentences(text: str) -> list[tuple[int, int, str]]:
    """Return deterministic, line-aware ``(paragraph, sentence, text)`` units.

    PDF table extraction commonly produces pages as one paragraph with one
    value per line. Treating that whole page as a sentence creates a clique of
    false relationships, so line breaks are locality boundaries as well as
    punctuation boundaries. Short table labels are retained because they can
    still support a nearby relationship.
    """
    units: list[tuple[int, int, str]] = []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    for paragraph_index, paragraph in enumerate(paragraphs):
        fragments = [
            fragment.strip()
            for fragment in re.split(r"(?<=[.!?])\s+|\n+", paragraph)
            if fragment.strip()
        ]
        if not fragments:
            fragments = [paragraph]
        sentence_index = 0
        for fragment in fragments:
            # Header/footer artifacts are useful for parsing but not for
            # inferred concept links.
            if _NOISE_LINE_RE.match(fragment) and len(fragment.split()) <= 6:
                continue
            units.append((paragraph_index, sentence_index, fragment))
            sentence_index += 1
    return units


def _candidate_names(entities: list[str | dict] | list[Keyword]) -> list[str]:
    """Normalize, deduplicate, and retain only usable candidate endpoint names."""
    names: set[str] = set()
    for entity in entities:
        if isinstance(entity, str):
            value = entity
        elif isinstance(entity, dict):
            value = str(entity.get("name", ""))
        else:
            value = getattr(entity, "name", "")
        name = normalize_keyword(value)
        if (
            name
            and len(name) >= 3
            and not re.fullmatch(r"[0-9\W]+", name)
            and is_usable_entity_name(name)
        ):
            names.add(name)
    return sorted(names)


def document_link_candidates(
    full_text: str,
    entities: list[str | dict] | list[Keyword],
    *,
    min_score: int = 2,
    window_sentences: int = 2,
    max_evidence: int = 3,
) -> list[dict]:
    """Link known entities using deterministic full-document locality.

    Endpoints are validated against the document before any pair is emitted.
    Sentence support is strongest, adjacent-sentence window support recovers
    links split by punctuation, and paragraph support rewards repeated local
    mentions without connecting every entity in a long paragraph. The score is
    deliberately explainable and deterministic::

        score = 3 * sentence_support + 2 * window_support + paragraph_support

    A pair qualifies when it has direct/window support, or repeated paragraph
    support. Each result is explicitly an undirected ``association`` with
    evidence pointing back to the paragraph/sentence that supported it.
    """
    if not full_text or not full_text.strip() or not entities:
        return []
    names = _candidate_names(entities)
    lower_text = full_text.lower()
    names = [name for name in names if _in_text(name, lower_text)]
    if len(names) < 2:
        return []

    units = _paragraphs_and_sentences(full_text)
    if not units:
        return []

    # Mentioned names for each sentence, paragraph, and sliding sentence window.
    sentence_mentions: list[tuple[int, int, str, list[str]]] = []
    for paragraph_index, sentence_index, sentence in units:
        lower_sentence = sentence.lower()
        present = [name for name in names if _in_text(name, lower_sentence)]
        if present:
            sentence_mentions.append((paragraph_index, sentence_index, sentence, present))

    paragraph_mentions: dict[int, set[str]] = {}
    paragraph_text: dict[int, str] = {}
    for paragraph_index, _sentence_index, sentence in units:
        paragraph_mentions.setdefault(paragraph_index, set()).update(
            name for name in names if _in_text(name, sentence.lower())
        )
        paragraph_text.setdefault(paragraph_index, sentence)
        if paragraph_text[paragraph_index] != sentence:
            paragraph_text[paragraph_index] += " " + sentence

    sentence_support: dict[tuple[str, str], int] = {}
    window_support: dict[tuple[str, str], int] = {}
    paragraph_support: dict[tuple[str, str], int] = {}
    evidence: dict[tuple[str, str], list[tuple[int, int, str]]] = {}

    def add_evidence(pair: tuple[str, str], paragraph_index: int, sentence_index: int, text: str) -> None:
        items = evidence.setdefault(pair, [])
        item = (paragraph_index, sentence_index, text.strip()[:300])
        if item not in items:
            items.append(item)
            items.sort(key=lambda value: (value[0], value[1], value[2]))
            del items[max_evidence:]

    def pairs(present: list[str]) -> list[tuple[str, str]]:
        return [
            (present[i], present[j]) if present[i] < present[j] else (present[j], present[i])
            for i in range(len(present))
            for j in range(i + 1, len(present))
            if present[i] != present[j]
        ]

    for paragraph_index, sentence_index, sentence, present in sentence_mentions:
        for pair in pairs(present):
            sentence_support[pair] = sentence_support.get(pair, 0) + 1
            add_evidence(pair, paragraph_index, sentence_index, sentence)

    # Sliding windows are built from the ordered document units, not only from
    # sentences that contain entities, so sentence gaps remain meaningful. Cap
    # this secondary signal: overlapping windows are evidence of locality, not
    # repeated independent claims.
    for start in range(max(0, len(units) - window_sentences + 1)):
        window = units[start : start + window_sentences]
        present = sorted(
            {
                name
                for _paragraph_index, _sentence_index, sentence in window
                for name in names
                if _in_text(name, sentence.lower())
            }
        )
        window_text = " ".join(sentence for _p, _s, sentence in window)
        for pair in pairs(present):
            window_support[pair] = min(3, window_support.get(pair, 0) + 1)
            add_evidence(pair, window[0][0], window[0][1], window_text)

    for paragraph_index, present in sorted(paragraph_mentions.items()):
        # A single long paragraph with many unrelated keywords is noisy. Allow
        # it as a local signal only when compact, or when repeated paragraphs
        # independently support the same pair.
        if len(present) > 8:
            continue
        paragraph_present = sorted(present)
        for pair in pairs(paragraph_present):
            paragraph_support[pair] = paragraph_support.get(pair, 0) + 1
            add_evidence(pair, paragraph_index, 0, paragraph_text[paragraph_index])

    all_pairs = sorted(set(sentence_support) | set(window_support) | set(paragraph_support))
    result: list[dict] = []
    window_only_min_support = 1 if len(units) <= 20 else 2
    for pair in all_pairs:
        sentence_count = sentence_support.get(pair, 0)
        window_count = window_support.get(pair, 0)
        paragraph_count = paragraph_support.get(pair, 0)
        score = 4 * sentence_count + 2 * window_count + paragraph_count
        if score < min_score or (
            sentence_count == 0
            and window_count < window_only_min_support
            and paragraph_count < 2
        ):
            continue
        support_count = sentence_count + window_count + paragraph_count
        items = [
            {
                "text": text,
                "source": "cooccurrence",
                "paragraph_index": paragraph_index,
                "sentence_index": sentence_index,
            }
            for paragraph_index, sentence_index, text in evidence.get(pair, [])
        ]
        result.append(
            {
                "source": pair[0],
                "target": pair[1],
                "relation": "co-occurs with",
                "tag": "cooccurrence",
                "direction": "undirected",
                "kind": "association",
                "weight": score,
                "support_count": support_count,
                "sentence_support": sentence_count,
                "window_support": window_count,
                "paragraph_support": paragraph_count,
                "snippet": items[0]["text"] if items else "",
                "evidence": items,
            }
        )
    # Keep the map readable: a strong concept may explain several neighbors,
    # but inferred locality should not turn it into a hairball. LLM assertions
    # are merged separately and are not subject to this statistical degree cap.
    result.sort(key=lambda edge: (-edge["weight"], edge["source"], edge["target"]))
    selected: list[dict] = []
    degree: dict[str, int] = {}
    for edge in result:
        source, target = edge["source"], edge["target"]
        if degree.get(source, 0) >= 8 or degree.get(target, 0) >= 8:
            continue
        selected.append(edge)
        degree[source] = degree.get(source, 0) + 1
        degree[target] = degree.get(target, 0) + 1
    return selected


def extract_statistical(
    chunks: list[str],
    full_text: str,
    max_keywords: int = 40,
    entity_names: list[str | dict] | None = None,
) -> dict:
    """Convenience: keywords + full-document association candidates.

    ``chunks`` remains accepted for pipeline compatibility and for callers that
    still need the legacy chunk-local helper. ``entity_names`` lets the pipeline
    add LLM endpoints to the candidate pool without requiring another extractor.
    """
    keywords = extract_keywords(full_text, max_keywords=max_keywords)
    if entity_names:
        llm_names = [normalize_keyword(str(entity.get("name", ""))) for entity in entity_names]
        # Prefer typed LLM concepts over a YAKE phrase that merely repeats or
        # extends the same name; statistical-only mode still keeps all usable
        # keywords when no LLM entities are available.
        keywords = [
            keyword
            for keyword in keywords
            if not any(
                keyword.name == llm_name
                or keyword.name in llm_name
                or llm_name in keyword.name
                for llm_name in llm_names
                if llm_name
            )
        ]
    candidates: list[str | dict] = list(keywords)
    candidates.extend(entity_names or [])
    return {
        "keywords": [k.__dict__ for k in keywords],
        "edges": document_link_candidates(full_text, candidates),
    }
