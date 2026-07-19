"""Deterministic query-aware QMSum context selection."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import math
import re
from typing import Any, Callable


_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?")
_NUMBER = re.compile(r"(?<!\w)[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?!\w)")
_ENTITY = re.compile(r"\b(?:[A-Z][A-Za-z0-9_-]*)(?:\s+[A-Z][A-Za-z0-9_-]*)*\b")
_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "that", "the", "their", "they", "to",
    "was", "were", "what", "when", "where", "which", "who", "why", "with",
}


@dataclass(frozen=True)
class TranscriptChunk:
    chunk_id: str
    source_start: int
    source_end: int
    text: str
    token_count: int


def _terms(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN.findall(text) if token.lower() not in _STOP]


def _entities(text: str) -> set[str]:
    return {value.lower() for value in _ENTITY.findall(text) if value.lower() not in _STOP}


def _numbers(text: str) -> set[str]:
    return {value.replace(",", "") for value in _NUMBER.findall(text)}


def _render_turn(turn: dict[str, Any]) -> str:
    speaker = str(turn.get("speaker", "unknown")).strip() or "unknown"
    content = str(turn.get("content", "")).strip()
    return f"{speaker}: {content}" if content else ""


def build_speaker_chunks(
    turns: list[dict[str, Any]],
    token_count: Callable[[str], int],
    *,
    target_tokens: int,
) -> list[TranscriptChunk]:
    if target_tokens < 1:
        raise ValueError("QMSum chunk target must be positive")
    rendered = [(index, _render_turn(turn)) for index, turn in enumerate(turns)]
    rendered = [(index, text) for index, text in rendered if text]
    chunks: list[TranscriptChunk] = []
    pending: list[tuple[int, str]] = []

    def flush() -> None:
        if not pending:
            return
        text = "\n".join(value for _, value in pending)
        chunks.append(
            TranscriptChunk(
                chunk_id=f"chunk-{len(chunks):04d}",
                source_start=pending[0][0],
                source_end=pending[-1][0],
                text=text,
                token_count=token_count(text),
            )
        )
        pending.clear()

    for source_index, text in rendered:
        candidate = "\n".join([*(value for _, value in pending), text])
        if pending and token_count(candidate) > target_tokens:
            flush()
        pending.append((source_index, text))
        # Oversized utterances remain intact: cutting them would silently alter
        # speaker evidence. They can be skipped later when enforcing budget.
        if token_count(text) >= target_tokens:
            flush()
    flush()
    return chunks


def _score_chunks(chunks: list[TranscriptChunk], query: str) -> list[tuple[float, TranscriptChunk]]:
    query_terms = _terms(query)
    query_set = set(query_terms)
    query_entities = _entities(query)
    query_numbers = _numbers(query)
    document_frequency = Counter()
    chunk_terms: dict[str, set[str]] = {}
    for chunk in chunks:
        values = set(_terms(chunk.text))
        chunk_terms[chunk.chunk_id] = values
        document_frequency.update(values)
    phrase = " ".join(query_terms)
    scored: list[tuple[float, TranscriptChunk]] = []
    for chunk in chunks:
        terms = chunk_terms[chunk.chunk_id]
        overlap = query_set & terms
        lexical = len(overlap) / max(1, len(query_set))
        rare = sum(math.log((len(chunks) + 1) / (document_frequency[term] + 1)) + 1 for term in overlap)
        rare /= max(1, len(query_set))
        entity = len(query_entities & _entities(chunk.text)) / max(1, len(query_entities))
        number = len(query_numbers & _numbers(chunk.text)) / max(1, len(query_numbers))
        phrase_match = 1.0 if len(query_terms) >= 2 and phrase in " ".join(_terms(chunk.text)) else 0.0
        score = 3.0 * lexical + 1.5 * rare + 2.0 * entity + 2.0 * number + phrase_match
        scored.append((score, chunk))
    return sorted(scored, key=lambda item: (-item[0], item[1].source_start, item[1].chunk_id))


def select_query_aware_context(
    turns: list[dict[str, Any]],
    query: str,
    token_count: Callable[[str], int],
    *,
    budget_tokens: int,
    chunk_target_tokens: int,
) -> tuple[str, dict[str, Any]]:
    if budget_tokens < 1:
        raise ValueError("QMSum context budget must be positive")
    chunks = build_speaker_chunks(turns, token_count, target_tokens=chunk_target_tokens)
    if not chunks:
        raise ValueError("QMSum meeting has no non-empty transcript content")
    full_context = "\n".join(_render_turn(turn) for turn in turns if _render_turn(turn))
    full_tokens = token_count(full_context)
    selected: list[TranscriptChunk] = []
    for _, chunk in _score_chunks(chunks, query):
        proposed = sorted([*selected, chunk], key=lambda value: value.source_start)
        proposed_text = "\n".join(value.text for value in proposed)
        if token_count(proposed_text) <= budget_tokens:
            selected = proposed
    if not selected:
        raise ValueError("no whole speaker chunk fits the configured QMSum token budget")
    selected.sort(key=lambda value: value.source_start)
    context = "\n".join(chunk.text for chunk in selected)
    selected_tokens = token_count(context)
    query_terms = set(_terms(query))
    query_entities = _entities(query)
    query_numbers = _numbers(query)
    context_terms = set(_terms(context))
    context_entities = _entities(context)
    context_numbers = _numbers(context)
    evidence = {
        "policy": "query_aware_budgeted",
        "budget_tokens": budget_tokens,
        "chunk_target_tokens": chunk_target_tokens,
        "full_transcript_token_count": full_tokens,
        "full_chunk_count": len(chunks),
        "selected_chunk_ids": [chunk.chunk_id for chunk in selected],
        "selected_source_ranges": [
            {"start_turn": chunk.source_start, "end_turn": chunk.source_end}
            for chunk in selected
        ],
        "selected_context_token_count": selected_tokens,
        "selection_keep_rate": selected_tokens / full_tokens if full_tokens else 1.0,
        "query_term_coverage": len(query_terms & context_terms) / max(1, len(query_terms)),
        "entity_coverage": len(query_entities & context_entities) / max(1, len(query_entities)),
        "number_coverage": len(query_numbers & context_numbers) / max(1, len(query_numbers)),
        "selected_context_sha256": hashlib.sha256(context.encode("utf-8")).hexdigest(),
    }
    return context, evidence


def reference_overlap_diagnostic(reference: str, context: str) -> float:
    reference_terms = set(_terms(reference))
    return len(reference_terms & set(_terms(context))) / max(1, len(reference_terms))
