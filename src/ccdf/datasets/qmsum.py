"""QMSum processing for Rec-T02A."""

from __future__ import annotations

from typing import Any

from ccdf.datasets.hashing import hash_json
from ccdf.datasets.schemas import validate_fixture

QUERY_POLICIES = {"specific_only", "general_only", "specific_and_general"}


def _meeting_id(raw: dict[str, Any], meeting_index: int) -> str:
    for key in ["meeting_id", "id", "meeting"]:
        if raw.get(key):
            return str(raw[key])
    return f"meeting{meeting_index:04d}"


def _turns(raw: dict[str, Any]) -> list[dict[str, str]]:
    turns = raw.get("meeting_transcripts")
    if not isinstance(turns, list) or not turns:
        raise ValueError("QMSum row missing meeting_transcripts")
    normalized: list[dict[str, str]] = []
    for turn in turns:
        speaker = str(turn.get("speaker", "unknown")).strip() or "unknown"
        content = str(turn.get("content", "")).strip()
        if content:
            normalized.append({"speaker": speaker, "content": content})
    if not normalized:
        raise ValueError("QMSum row has no non-empty transcript turns")
    return normalized


def _queries(raw: dict[str, Any], policy: str) -> list[tuple[str, int, dict[str, Any]]]:
    if policy not in QUERY_POLICIES:
        raise ValueError(f"invalid QMSum query policy: {policy}")
    selected: list[tuple[str, int, dict[str, Any]]] = []
    if policy in {"specific_only", "specific_and_general"}:
        selected.extend(("specific", idx, q) for idx, q in enumerate(raw.get("specific_query_list") or []))
    if policy in {"general_only", "specific_and_general"}:
        selected.extend(("general", idx, q) for idx, q in enumerate(raw.get("general_query_list") or []))
    if not selected:
        raise ValueError(f"QMSum row has no queries for policy {policy}")
    return selected


def _truncate_turns(
    turns: list[dict[str, str]], max_context_words: int | None
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    original_words = sum(len(turn["content"].split()) for turn in turns)
    if max_context_words is None or original_words <= max_context_words:
        return turns, {
            "truncated": False,
            "original_words": original_words,
            "retained_words": original_words,
            "boundary": "none",
            "strategy": "none",
            "caveat": "",
        }
    retained: list[dict[str, str]] = []
    count = 0
    for turn in turns:
        words = turn["content"].split()
        if count + len(words) > max_context_words:
            break
        retained.append(turn)
        count += len(words)
    if not retained:
        retained = [{"speaker": turns[0]["speaker"], "content": " ".join(turns[0]["content"].split()[:max_context_words])}]
        count = len(retained[0]["content"].split())
        boundary = "word"
    else:
        boundary = "utterance"
    return retained, {
        "truncated": True,
        "original_words": original_words,
        "retained_words": count,
        "boundary": boundary,
        "strategy": "prefix_preserve_turn_boundaries",
        "caveat": "Reference evidence may fall outside retained context.",
    }


def _render_context(turns: list[dict[str, str]]) -> str:
    return "\n".join(f"{turn['speaker']}: {turn['content']}" for turn in turns)


def build_fixtures(
    rows: list[dict[str, Any]],
    source_lock: dict[str, Any],
    *,
    query_policy: str = "specific_only",
    max_context_words: int | None = 1500,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fixtures: list[dict[str, Any]] = []
    truncation_rows: list[dict[str, Any]] = []
    for meeting_index, raw in enumerate(rows):
        meeting_id = _meeting_id(raw, meeting_index)
        turns = _turns(raw)
        selected_turns, truncation = _truncate_turns(turns, max_context_words)
        context = _render_context(selected_turns)
        for query_type, query_index, query in _queries(raw, query_policy):
            question = str(query["query"]).strip()
            reference = str(query["answer"]).strip()
            content = {
                "dataset": "qmsum",
                "split": "test",
                "meeting_id": meeting_id,
                "query_type": query_type,
                "query_index": query_index,
                "question": question,
                "reference_answer": reference,
                "turns": selected_turns,
                "truncation": truncation,
            }
            content_hash = hash_json(content)
            fixture_id = f"qmsum_test_{meeting_id}_{query_type}_{query_index:02d}_{content_hash[:8]}"
            instruction = "Answer using only the meeting transcript. A concise answer is enough."
            prompt = f"Meeting transcript:\n{context}\n\nQuestion:\n{question}\n\n{instruction}"
            row = {
                "fixture_id": fixture_id,
                "dataset": "qmsum",
                "split": "test",
                "content_hash": content_hash,
                "source_row_hash": hash_json(raw),
                "question": question,
                "reference_answer": reference,
                "prompt_parts": {
                    "context": context,
                    "question": question,
                    "instruction": instruction,
                    "system": None,
                },
                "prompt": prompt,
                "meeting": {"meeting_id": meeting_id, "turns": selected_turns},
                "qmsum_policy": {
                    "query_policy": query_policy,
                    "query_type": query_type,
                    "query_index": query_index,
                },
                "truncation": truncation,
                "lineage": {
                    "source_identity": source_lock["identity"],
                    "source_revision": source_lock["resolved_revision"],
                    "source_raw_sha256": source_lock["raw_sha256"],
                    "meeting_index": meeting_index,
                    "meeting_id": meeting_id,
                    "query_type": query_type,
                    "query_index": query_index,
                },
                "evaluation": {
                    "policy": "reference_precision_recall_proxy",
                    "semantic_correctness": "NOT_CLAIMED",
                },
            }
            validate_fixture(row)
            fixtures.append(row)
            truncation_rows.append(
                {
                    "fixture_id": fixture_id,
                    "meeting_id": meeting_id,
                    "query_type": query_type,
                    "query_index": query_index,
                    **truncation,
                }
            )
    ids = [fixture["fixture_id"] for fixture in fixtures]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate QMSum fixture id")
    return fixtures, truncation_rows
