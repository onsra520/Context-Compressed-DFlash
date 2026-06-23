from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

TARGET_FIXTURE_IDS = (
    "qmsum_meeting_qa_test_0036",
    "qmsum_meeting_qa_test_0070",
    "qmsum_meeting_qa_test_0055",
    "qmsum_meeting_qa_test_0078",
    "qmsum_meeting_qa_test_0094",
    "qmsum_meeting_qa_test_0001",
)

DEFAULT_INPUT = Path("data/eval/qmsum_meeting_qa_target_rows_task102f.jsonl")
DEFAULT_DATASET_OUTPUT = Path("data/eval/qmsum_meeting_qa_target_rows_task103a_evidence_selected.jsonl")
DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task103a_qmsum_evidence_selector_before_answer"
)

LEAKAGE_FIELDS = {
    "generated_text",
    "generated_output",
    "model_answer",
    "generated_answer",
    "prediction",
    "response",
    "output",
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "his",
    "how",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "may",
    "might",
    "not",
    "of",
    "on",
    "only",
    "or",
    "she",
    "should",
    "so",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "to",
    "use",
    "used",
    "using",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "with",
    "would",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_number} is not a JSON object")
        rows.append(payload)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _fixture_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("fixture_id") or row.get("dataset_id") or "")


def _tokens(text: Any) -> list[str]:
    raw = re.findall(r"[A-Za-z0-9]+", str(text or "").lower())
    return [token for token in raw if token not in STOPWORDS and len(token) > 1]


def _entity_number_terms(text: Any) -> set[str]:
    source = str(text or "")
    terms = set(re.findall(r"\b[A-Z][A-Za-z0-9-]*\b|\b[A-Z]{2,}\b|\b\d+(?:\.\d+)?\b", source))
    return {term.lower() for term in terms if term.lower() not in STOPWORDS}


def validate_source_rows(rows: list[dict[str, Any]], *, expected_ids: tuple[str, ...] = TARGET_FIXTURE_IDS) -> dict[str, Any]:
    errors: list[str] = []
    ids = [_fixture_id(row) for row in rows]
    expected = set(expected_ids)
    if len(rows) != len(expected_ids):
        errors.append(f"expected {len(expected_ids)} rows, found {len(rows)}")
    if set(ids) != expected:
        errors.append(f"fixture id mismatch: {sorted(set(ids))}")
    if len(ids) != len(set(ids)):
        errors.append("duplicate fixture_id found")
    for row in rows:
        fixture_id = _fixture_id(row)
        missing = [field for field in ("context", "question", "expected_answer") if not str(row.get(field) or "").strip()]
        if missing:
            errors.append(f"{fixture_id} missing required fields: {missing}")
        leaked = sorted(LEAKAGE_FIELDS & set(row))
        if leaked:
            errors.append(f"{fixture_id} generated-output fields present: {leaked}")
    return {"valid": not errors, "errors": errors, "row_count": len(rows), "fixture_ids": ids}


def split_windows(context: str, *, max_window_chars: int = 520) -> list[str]:
    segments = [
        segment.strip()
        for segment in re.split(r"(?=\b(?:Speaker|Professor|PhD|Grad|Project Manager|User Interface Designer|Marketing Expert|Industrial Designer)\b[^:]{0,80}:)", str(context or ""))
        if segment.strip()
    ]
    if not segments:
        segments = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", str(context or "")) if segment.strip()]
    windows: list[str] = []
    current = ""
    for segment in segments:
        if current and len(current) + len(segment) + 1 > max_window_chars:
            windows.append(current.strip())
            current = segment
        else:
            current = f"{current} {segment}".strip()
    if current:
        windows.append(current.strip())
    return windows


def score_window(window: str, question: str) -> dict[str, Any]:
    question_tokens = set(_tokens(question))
    window_tokens = set(_tokens(window))
    question_entities = _entity_number_terms(question)
    window_entities = _entity_number_terms(window)
    overlap = question_tokens & window_tokens
    entity_overlap = question_entities & window_entities
    action_terms = {
        "approve",
        "approved",
        "disapprove",
        "discuss",
        "discussed",
        "decide",
        "decided",
        "suggest",
        "suggested",
        "reason",
        "reasons",
        "impact",
        "training",
        "latency",
        "spectral",
        "space",
        "groups",
    }
    action_overlap = action_terms & window_tokens
    score = (3.0 * len(overlap)) + (4.0 * len(entity_overlap)) + (1.5 * len(action_overlap))
    return {
        "score": round(score, 6),
        "question_overlap_terms": sorted(overlap),
        "entity_number_overlap_terms": sorted(entity_overlap),
        "action_overlap_terms": sorted(action_overlap),
        "window_chars": len(window),
    }


def select_evidence(row: dict[str, Any], *, top_k: int = 5, max_chars: int = 2600) -> dict[str, Any]:
    question = str(row.get("question") or "")
    windows = split_windows(str(row.get("context") or ""))
    scored = []
    for index, window in enumerate(windows):
        metrics = score_window(window, question)
        scored.append({"window_index": index, "text": window, **metrics})
    scored.sort(key=lambda item: (-float(item["score"]), int(item["window_index"])))
    selected: list[dict[str, Any]] = []
    used_chars = 0
    prefix_budget = 16
    for item in scored:
        if len(selected) >= top_k:
            break
        if item["score"] <= 0 and selected:
            continue
        remaining = max_chars - used_chars - prefix_budget
        if remaining <= 0:
            break
        text = str(item["text"])
        if len(text) > remaining:
            text = text[: max(1, remaining - 3)].rstrip() + "..."
        if used_chars + len(text) > max_chars and selected:
            continue
        selected.append({**item, "text": text, "window_chars": len(text), "truncated_for_budget": len(text) < len(str(item["text"]))})
        used_chars += len(text) + prefix_budget
    if not selected and scored:
        selected.append(scored[0])
    selected.sort(key=lambda item: int(item["window_index"]))
    evidence_context = "\n\n".join(f"[evidence {idx + 1}] {item['text']}" for idx, item in enumerate(selected))
    return {
        "fixture_id": _fixture_id(row),
        "question": question,
        "selected_context": evidence_context,
        "selected_snippets": selected,
        "window_count": len(windows),
        "selected_count": len(selected),
        "selected_chars": len(evidence_context),
        "max_chars": max_chars,
        "top_k": top_k,
    }


def _dataset_row_from_selection(source_row: dict[str, Any], selection: dict[str, Any]) -> dict[str, Any]:
    fixture_id = _fixture_id(source_row)
    context = str(selection["selected_context"])
    question = str(source_row["question"])
    return {
        "id": fixture_id,
        "dataset_name": "qmsum_meeting_qa_long",
        "context": context,
        "question": question,
        "expected_answer": str(source_row["expected_answer"]),
        "ground_truth_answer": str(source_row.get("ground_truth_answer") or source_row["expected_answer"]),
        "prompt": f"Selected meeting evidence:\n{context}\n\nQuestion: {question}",
        "domain": str(source_row.get("domain") or "meeting_qa_long_context"),
        "evidence": "Task103A deterministic question-focused selected evidence. Reference answer was not used for retrieval.",
        "approximate_context_words": len(str(context).split()),
        "quality_policy": str(source_row.get("quality_policy") or "normalized_text_containment_proxy"),
        "selector_metadata": {
            "selector_name": "task103a_question_focused_evidence_selector_v1",
            "reference_used_for_retrieval": False,
            "prior_generated_outputs_used": False,
            "selected_count": selection["selected_count"],
            "selected_chars": selection["selected_chars"],
            "window_count": selection["window_count"],
            "top_k": selection["top_k"],
            "max_chars": selection["max_chars"],
        },
    }


def build_evidence_selected_dataset(
    *,
    input_path: Path = DEFAULT_INPUT,
    dataset_output_path: Path = DEFAULT_DATASET_OUTPUT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    expected_ids: tuple[str, ...] = TARGET_FIXTURE_IDS,
    max_chars: int = 2600,
    top_k: int = 5,
) -> dict[str, Any]:
    rows = read_jsonl(input_path)
    audit = validate_source_rows(rows, expected_ids=expected_ids)
    if not audit["valid"]:
        raise ValueError(f"source row validation failed: {audit['errors']}")
    selected_records: list[dict[str, Any]] = []
    dataset_rows: list[dict[str, Any]] = []
    for row in rows:
        selection = select_evidence(row, top_k=top_k, max_chars=max_chars)
        selected_records.append(
            {
                "fixture_id": selection["fixture_id"],
                "question": selection["question"],
                "selected_context": selection["selected_context"],
                "selected_snippets": selection["selected_snippets"],
                "selected_count": selection["selected_count"],
                "selected_chars": selection["selected_chars"],
                "window_count": selection["window_count"],
                "reference_used_for_retrieval": False,
                "prior_generated_outputs_used": False,
            }
        )
        dataset_rows.append(_dataset_row_from_selection(row, selection))
    summary = {
        "task": "T103A — QMSum Evidence Retrieval / Evidence Selector before Answer",
        "selector_name": "task103a_question_focused_evidence_selector_v1",
        "row_count": len(dataset_rows),
        "input_path": str(input_path),
        "dataset_output_path": str(dataset_output_path),
        "source_validation": audit,
        "max_chars": max_chars,
        "top_k": top_k,
        "reference_used_for_retrieval": False,
        "prior_generated_outputs_used": False,
        "selected_chars_by_fixture": {
            record["fixture_id"]: record["selected_chars"] for record in selected_records
        },
    }
    write_jsonl(dataset_output_path, dataset_rows)
    write_json(output_dir / "summary/task103a_selector_summary.json", summary)
    write_jsonl(output_dir / "summary/task103a_selected_evidence.jsonl", selected_records)
    return {"summary": summary, "selected_records": selected_records, "dataset_rows": dataset_rows}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Task103A QMSum question-focused evidence-selected dataset.")
    parser.add_argument("--input-path", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dataset-output-path", type=Path, default=DEFAULT_DATASET_OUTPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-chars", type=int, default=2600)
    parser.add_argument("--top-k", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_evidence_selected_dataset(
        input_path=args.input_path,
        dataset_output_path=args.dataset_output_path,
        output_dir=args.output_dir,
        max_chars=args.max_chars,
        top_k=args.top_k,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
