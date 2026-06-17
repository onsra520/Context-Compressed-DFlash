from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ccdf.compression.llmlingua import LLMLinguaCompressor
from ccdf.config import load_config
from scripts.phase_1_analysis.analyze_task70_qmsum_diagnostic_audit import load_jsonl
from scripts.phase_1_analysis.analyze_task76_qmsum_evidence_error_taxonomy import (
    NOISY_ENTITY_WORDS,
    _entities_and_numbers,
)
from scripts.eval_datasets import QMSUM_EVIDENCE_FOCUSED_ANSWER_INSTRUCTION, select_eval_dataset_rows
from scripts.run_mvp import _append_protected_suffix, _preview_text, _tail_preview_text, _without_suffix

DEFAULT_CASE_INPUT = Path("results/task77_qmsum_evidence_policy_cases.jsonl")
DEFAULT_LLMLINGUA_ARTIFACT = Path("results/task77_qmsum_long_llmlingua_ar_r2_n30_mnt384_evidence.jsonl")
DEFAULT_CC_DFLASH_ARTIFACT = Path("results/task77_qmsum_long_cc_dflash_r2_n30_mnt384_evidence.jsonl")
DEFAULT_SUMMARY_OUTPUT = Path("results/task78_qmsum_evidence_retention_summary.json")
DEFAULT_TABLE_OUTPUT = Path("results/task78_qmsum_evidence_retention_table.csv")
DEFAULT_CASES_OUTPUT = Path("results/task78_qmsum_evidence_retention_cases.jsonl")
DEFAULT_RECONSTRUCTED_OUTPUT = Path("results/task78_qmsum_reconstructed_prompt_previews.jsonl")
DEFAULT_SPANS_OUTPUT = Path("results/task78_qmsum_selected_evidence_spans.jsonl")

PRIORITY_PROMPT_IDS = [14, 20, 23, 27, 28, 30]
SECONDARY_PROMPT_IDS = [4, 8, 13, 21]
NON_FAILURE_LABELS = {"ACCEPTABLE_EVIDENCE_FOCUSED_ANSWER", "PROXY_WEAKNESS"}
DOMAIN_PHRASES = [
    "Welsh Government",
    "British Columbia",
    "anti-oil lobby",
    "anti-oil and gas lobby",
    "anti-oil/gas lobby",
    "oil sands",
    "Bill C-69",
    "Bill C-48",
    "disk rack",
    "speech recognition",
    "gesture recognition",
    "research cooperation",
    "remote areas",
    "solar energy alimentation",
    "production cost",
    "police and crime commissioners",
    "fishing industry",
    "fish and seafood",
    "input delta",
]
EXTRA_NOISY_WORDS = {
    "These",
    "Beyond",
    "Next",
    "Then",
    "For",
    "It",
    "More",
    "User",
}


def _compact(text: Any, limit: int = 420) -> str:
    if not isinstance(text, str):
        return ""
    clean = " ".join(text.split())
    return clean[:limit] + ("..." if len(clean) > limit else "")


def _term_present(term: str, text: str) -> bool:
    clean_text = str(text or "").lower().replace(",", "")
    clean_term = str(term or "").lower().replace(",", "")
    candidates = {
        clean_term,
        clean_term.replace("$", ""),
        clean_term.replace(" ", ""),
        clean_term.replace("-", " "),
    }
    return any(candidate and candidate in clean_text for candidate in candidates)


def extract_important_terms(expected_answer: Any) -> list[str]:
    text = str(expected_answer or "")
    seen: set[str] = set()
    terms: list[str] = []

    for phrase in DOMAIN_PHRASES:
        if re.search(re.escape(phrase), text, flags=re.IGNORECASE):
            key = phrase.lower()
            if key not in seen:
                seen.add(key)
                terms.append(phrase)

    for item in _entities_and_numbers(text):
        if item in NOISY_ENTITY_WORDS or item in EXTRA_NOISY_WORDS:
            continue
        item = re.sub(r"^\$?(-?\d+(?:\.\d+)?)M$", r"\1", item)
        key = item.lower()
        if key not in seen:
            seen.add(key)
            terms.append(item)

    return terms


def _hits(terms: list[str], text: str) -> list[str]:
    return [term for term in terms if _term_present(term, text)]


def classify_retention(
    *,
    expected_answer: str,
    original_context: str | None,
    compressed_context: str | None,
    question_preserved: bool,
    protected_suffix_preserved: bool,
    reconstructed: bool = True,
) -> dict[str, Any]:
    terms = extract_important_terms(expected_answer)
    original_available = isinstance(original_context, str) and bool(original_context.strip())
    compressed_available = isinstance(compressed_context, str) and bool(compressed_context.strip())
    original_hits = _hits(terms, original_context or "")
    compressed_hits = _hits(terms, compressed_context or "")
    original_rate = len(original_hits) / len(terms) if terms else 0.0
    compressed_rate = len(compressed_hits) / len(terms) if terms else 0.0
    lost_terms = [term for term in original_hits if term not in compressed_hits]
    retained_terms = [term for term in compressed_hits if term in original_hits or not original_hits]
    retention_ratio = compressed_rate / original_rate if original_rate > 0 else 0.0

    if not question_preserved or not protected_suffix_preserved:
        label = "QUESTION_OR_SUFFIX_LOSS"
        confidence = "high"
        rationale = "Question or protected suffix was not preserved."
    elif not reconstructed and (not original_available or not compressed_available):
        label = "PREVIEW_INSUFFICIENT_NEEDS_FULL_RECONSTRUCTION"
        confidence = "low"
        rationale = "Artifact previews are insufficient for evidence-retention classification."
    elif terms and original_rate < 0.25:
        label = "EVIDENCE_MISSING_FROM_ORIGINAL_CONTEXT_OR_SOURCE_MISMATCH"
        confidence = "medium" if original_available else "low"
        rationale = "Expected evidence terms were not found in the original context, suggesting source mismatch or extraction limitation."
    elif terms and original_rate >= 0.25 and compressed_rate < 0.25:
        label = "EVIDENCE_MISSING_FROM_COMPRESSED_PROMPT"
        confidence = "high" if reconstructed else "medium"
        rationale = "Expected evidence appears in original context but not in compressed context."
    elif terms and compressed_rate >= 0.70:
        label = "EVIDENCE_PRESENT_IN_COMPRESSED_PROMPT_MODEL_FAILED"
        confidence = "high" if reconstructed else "medium"
        rationale = "Most expected evidence terms are present after compression, but Task 77 output still failed."
    elif terms and compressed_rate >= 0.35:
        label = "EVIDENCE_PARTIALLY_PRESENT_IN_COMPRESSED_PROMPT"
        confidence = "medium"
        rationale = "Some expected evidence survives compression, but important terms are missing or fragmented."
    elif not terms:
        label = "UNCLEAR"
        confidence = "low"
        rationale = "No robust expected evidence terms were extracted."
    else:
        label = "UNCLEAR"
        confidence = "low"
        rationale = "Heuristic evidence-retention checks are inconclusive."

    return {
        "important_expected_terms": terms,
        "original_context_available": original_available,
        "compressed_context_available": compressed_available,
        "original_context_term_hits": original_hits,
        "compressed_context_term_hits": compressed_hits,
        "original_context_hit_rate": round(original_rate, 6),
        "compressed_context_hit_rate": round(compressed_rate, 6),
        "avg_evidence_retention_ratio": round(retention_ratio, 6),
        "lost_terms_after_compression": lost_terms,
        "retained_terms_after_compression": retained_terms,
        "question_preserved": bool(question_preserved),
        "protected_suffix_preserved": bool(protected_suffix_preserved),
        "evidence_retention_label": label,
        "confidence": confidence,
        "rationale": rationale,
    }


def _group_cases_by_prompt(task77_cases: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for case in task77_cases:
        prompt_id = case.get("prompt_id")
        if isinstance(prompt_id, int) and not isinstance(prompt_id, bool):
            grouped[prompt_id].append(case)
    return dict(grouped)


def _selected_prompt_ids(grouped_cases: dict[int, list[dict[str, Any]]]) -> list[int]:
    selected = set(PRIORITY_PROMPT_IDS + SECONDARY_PROMPT_IDS)
    for prompt_id, cases in grouped_cases.items():
        if any(case.get("task77_evidence_error_label") not in NON_FAILURE_LABELS for case in cases):
            selected.add(prompt_id)
    return sorted(selected)


def _artifact_by_condition_prompt(rows_by_condition: dict[str, list[dict[str, Any]]]) -> dict[tuple[str, int], dict[str, Any]]:
    lookup: dict[tuple[str, int], dict[str, Any]] = {}
    for condition, rows in rows_by_condition.items():
        for row in rows:
            prompt_id = row.get("benchmark_prompt_index", row.get("prompt_id"))
            if isinstance(prompt_id, int) and not isinstance(prompt_id, bool):
                lookup[(condition, prompt_id)] = row
    return lookup


def _case_output(
    prompt_id: int,
    cases: list[dict[str, Any]],
    *,
    artifact_lookup: dict[tuple[str, int], dict[str, Any]],
    reconstruction: dict[str, Any] | None,
) -> dict[str, Any]:
    first = cases[0]
    expected = str(first.get("expected_answer") or "")
    labels_by_condition = {
        str(case.get("condition")): case.get("task77_evidence_error_label")
        for case in cases
        if case.get("condition")
    }
    generated_by_condition = {
        str(case.get("condition")): _compact(case.get("task77_generated_snippet"), 300)
        for case in cases
        if case.get("condition")
    }
    artifact_rows = [
        artifact_lookup.get((condition, prompt_id))
        for condition in labels_by_condition
        if artifact_lookup.get((condition, prompt_id)) is not None
    ]
    question_preserved = all(row.get("question_preserved") is True for row in artifact_rows) if artifact_rows else False
    suffix_preserved = all(row.get("protected_suffix_preserved") is True for row in artifact_rows) if artifact_rows else False
    original_context = None
    compressed_context = None
    reconstructed = False
    if reconstruction is not None:
        original_context = reconstruction.get("original_context")
        compressed_context = reconstruction.get("compressed_context")
        question_preserved = bool(reconstruction.get("question_preserved", question_preserved))
        suffix_preserved = bool(reconstruction.get("protected_suffix_preserved", suffix_preserved))
        reconstructed = True
    elif artifact_rows:
        original_context = artifact_rows[0].get("original_context_preview")
        compressed_context = artifact_rows[0].get("compressed_context_preview")

    classified = classify_retention(
        expected_answer=expected,
        original_context=original_context,
        compressed_context=compressed_context,
        question_preserved=question_preserved,
        protected_suffix_preserved=suffix_preserved,
        reconstructed=reconstructed,
    )
    label = classified["evidence_retention_label"]
    if label == "EVIDENCE_MISSING_FROM_COMPRESSED_PROMPT":
        next_action = "Audit compression strategy, keep-rate, or evidence-aware compression for this prompt."
    elif label == "EVIDENCE_PRESENT_IN_COMPRESSED_PROMPT_MODEL_FAILED":
        next_action = "Treat as model locating/answering failure; consider manual/semantic review or retrieval/reranking."
    elif label == "EVIDENCE_MISSING_FROM_ORIGINAL_CONTEXT_OR_SOURCE_MISMATCH":
        next_action = "Audit dataset/reference alignment for this prompt."
    elif label == "PREVIEW_INSUFFICIENT_NEEDS_FULL_RECONSTRUCTION":
        next_action = "Export or reconstruct full prompt/context before drawing conclusions."
    else:
        next_action = "Keep case in Task 78 limitation set for manual review."

    return {
        "prompt_id": prompt_id,
        "fixture_id": first.get("fixture_id"),
        "condition": "shared_compressed_prompt",
        "task77_label_by_condition": labels_by_condition,
        "expected_answer": _compact(expected, 640),
        "generated_text_snippets_by_condition": generated_by_condition,
        **classified,
        "rationale": classified["rationale"],
        "recommended_next_action": next_action,
    }


def analyze_retention(
    task77_cases: list[dict[str, Any]],
    *,
    reconstructed_by_prompt: dict[int, dict[str, Any]] | None = None,
    task77_artifacts_by_condition: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    grouped = _group_cases_by_prompt(task77_cases)
    selected = _selected_prompt_ids(grouped)
    artifact_lookup = _artifact_by_condition_prompt(task77_artifacts_by_condition or {})
    cases = [
        _case_output(
            prompt_id,
            grouped[prompt_id],
            artifact_lookup=artifact_lookup,
            reconstruction=(reconstructed_by_prompt or {}).get(prompt_id),
        )
        for prompt_id in selected
        if prompt_id in grouped
    ]
    label_counts = Counter(case["evidence_retention_label"] for case in cases)
    question_preserved_count = sum(1 for case in cases if case["question_preserved"])
    suffix_preserved_count = sum(1 for case in cases if case["protected_suffix_preserved"])
    original_rates = [case["original_context_hit_rate"] for case in cases]
    compressed_rates = [case["compressed_context_hit_rate"] for case in cases]
    retention_ratios = [case["avg_evidence_retention_ratio"] for case in cases]
    reconstructed_count = sum(
        1 for case in cases if case["original_context_available"] and case["compressed_context_available"]
    )
    summary = {
        "status": "PASS_WITH_NOTES",
        "total_audited_cases": len(cases),
        "audited_priority_cases": sum(1 for case in cases if case["prompt_id"] in PRIORITY_PROMPT_IDS),
        "audited_secondary_cases": sum(1 for case in cases if case["prompt_id"] in SECONDARY_PROMPT_IDS),
        "rows_with_full_reconstruction": reconstructed_count,
        "rows_artifact_only": len(cases) - reconstructed_count,
        "question_preserved_count": question_preserved_count,
        "suffix_preserved_count": suffix_preserved_count,
        "avg_original_evidence_hit_rate": round(statistics.fmean(original_rates), 6) if original_rates else 0.0,
        "avg_compressed_evidence_hit_rate": round(statistics.fmean(compressed_rates), 6) if compressed_rates else 0.0,
        "avg_evidence_retention_ratio": round(statistics.fmean(retention_ratios), 6) if retention_ratios else 0.0,
        "count_by_evidence_retention_label": dict(sorted(label_counts.items())),
        "cases_where_evidence_present_but_model_failed": [
            case["prompt_id"]
            for case in cases
            if case["evidence_retention_label"] == "EVIDENCE_PRESENT_IN_COMPRESSED_PROMPT_MODEL_FAILED"
        ],
        "cases_where_evidence_missing_after_compression": [
            case["prompt_id"]
            for case in cases
            if case["evidence_retention_label"] == "EVIDENCE_MISSING_FROM_COMPRESSED_PROMPT"
        ],
        "cases_needing_full_reconstruction": [
            case["prompt_id"]
            for case in cases
            if case["evidence_retention_label"] == "PREVIEW_INSUFFICIENT_NEEDS_FULL_RECONSTRUCTION"
        ],
        "possible_dataset_reference_mismatch_prompt_ids": [
            case["prompt_id"]
            for case in cases
            if case["evidence_retention_label"] == "EVIDENCE_MISSING_FROM_ORIGINAL_CONTEXT_OR_SOURCE_MISMATCH"
        ],
        "specific_prompt_checks": {
            str(prompt_id): [case for case in cases if case["prompt_id"] == prompt_id]
            for prompt_id in PRIORITY_PROMPT_IDS
        },
        "secondary_prompt_checks": {
            str(prompt_id): [case for case in cases if case["prompt_id"] == prompt_id]
            for prompt_id in SECONDARY_PROMPT_IDS
        },
        "decisions": _decisions(label_counts),
    }
    table = [
        {
            "evidence_retention_label": label,
            "count": count,
            "prompt_ids": ",".join(
                str(case["prompt_id"]) for case in cases if case["evidence_retention_label"] == label
            ),
        }
        for label, count in sorted(label_counts.items())
    ]
    return summary, table, cases


def _decisions(label_counts: Counter[str]) -> dict[str, Any]:
    missing = label_counts["EVIDENCE_MISSING_FROM_COMPRESSED_PROMPT"]
    partial = label_counts["EVIDENCE_PARTIALLY_PRESENT_IN_COMPRESSED_PROMPT"]
    present_failed = label_counts["EVIDENCE_PRESENT_IN_COMPRESSED_PROMPT_MODEL_FAILED"]
    source_mismatch = label_counts["EVIDENCE_MISSING_FROM_ORIGINAL_CONTEXT_OR_SOURCE_MISMATCH"]
    insufficient = label_counts["PREVIEW_INSUFFICIENT_NEEDS_FULL_RECONSTRUCTION"]
    if missing + partial > present_failed:
        next_task = "Task 79A compression/evidence-retention mitigation"
        conclusion = "compression_evidence_loss_or_partial_retention"
    elif present_failed > 0:
        next_task = "Task 79B final QMSum limitation freeze / reporting decision"
        conclusion = "model_failure_despite_retained_evidence"
    elif insufficient > 0:
        next_task = "Task 79 full prompt debug export"
        conclusion = "insufficient_artifacts"
    elif source_mismatch > 0:
        next_task = "Task 79 dataset/reference alignment audit"
        conclusion = "possible_dataset_reference_mismatch"
    else:
        next_task = "Task 79B final QMSum limitation freeze / reporting decision"
        conclusion = "unclear"
    return {
        "main_conclusion": conclusion,
        "recommended_next_task": next_task,
        "mnt512_needed": False,
        "qmsum_n100_justified": False,
        "continue_suffix_prompt_tuning": False,
    }


def reconstruct_selected_prompts(
    prompt_ids: list[int],
    *,
    config_path: Path,
    seed: int,
    n: int,
    keep_rate: float,
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    config = load_config(config_path)
    rows = select_eval_dataset_rows("qmsum_meeting_qa_long", n=n, seed=seed)
    compressor = LLMLinguaCompressor.from_config(config)
    reconstructed: dict[int, dict[str, Any]] = {}
    preview_rows: list[dict[str, Any]] = []
    span_rows: list[dict[str, Any]] = []
    for prompt_id in prompt_ids:
        if not 1 <= prompt_id <= len(rows):
            continue
        row = rows[prompt_id - 1]
        merged_prompt, info = compressor.compress(context=row.context, question=row.question, keep_rate=keep_rate)
        compressed_context = _without_suffix(merged_prompt, row.question)
        final_prompt = _append_protected_suffix(merged_prompt, QMSUM_EVIDENCE_FOCUSED_ANSWER_INSTRUCTION)
        question_preserved = row.question in final_prompt
        suffix_preserved = QMSUM_EVIDENCE_FOCUSED_ANSWER_INSTRUCTION in final_prompt
        reconstructed[prompt_id] = {
            "fixture_id": row.id,
            "original_context": row.context,
            "compressed_context": compressed_context,
            "question_preserved": question_preserved,
            "protected_suffix_preserved": suffix_preserved,
            "compressor_info": info,
        }
        terms = extract_important_terms(row.expected_answer)
        original_hits = _hits(terms, row.context)
        compressed_hits = _hits(terms, compressed_context)
        preview_rows.append(
            {
                "prompt_id": prompt_id,
                "fixture_id": row.id,
                "original_context_preview": _preview_text(row.context, limit=500),
                "compressed_context_preview": _preview_text(compressed_context, limit=500),
                "final_prompt_tail_preview": _tail_preview_text(final_prompt, limit=640),
                "question_preserved": question_preserved,
                "protected_suffix_preserved": suffix_preserved,
                "N_original": info.get("N_original"),
                "N_compressed": info.get("N_compressed"),
                "R_actual": info.get("R_actual"),
            }
        )
        span_rows.append(
            {
                "prompt_id": prompt_id,
                "fixture_id": row.id,
                "important_expected_terms": terms,
                "original_context_term_hits": original_hits,
                "compressed_context_term_hits": compressed_hits,
                "lost_terms_after_compression": [term for term in original_hits if term not in compressed_hits],
            }
        )
    return reconstructed, preview_rows, span_rows


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 78 QMSum compressed-prompt evidence retention")
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument("--case-input", type=Path, default=DEFAULT_CASE_INPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--table-output", type=Path, default=DEFAULT_TABLE_OUTPUT)
    parser.add_argument("--cases-output", type=Path, default=DEFAULT_CASES_OUTPUT)
    parser.add_argument("--reconstructed-output", type=Path, default=DEFAULT_RECONSTRUCTED_OUTPUT)
    parser.add_argument("--spans-output", type=Path, default=DEFAULT_SPANS_OUTPUT)
    parser.add_argument("--no-reconstruct", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--keep-rate", type=float, default=0.5)
    args = parser.parse_args()

    task77_cases = load_jsonl(args.case_input)
    artifacts = {
        "LLMLingua-AR-R2": load_jsonl(DEFAULT_LLMLINGUA_ARTIFACT),
        "CC-DFlash-R2": load_jsonl(DEFAULT_CC_DFLASH_ARTIFACT),
    }
    grouped = _group_cases_by_prompt(task77_cases)
    selected = _selected_prompt_ids(grouped)
    reconstructed: dict[int, dict[str, Any]] | None = None
    preview_rows: list[dict[str, Any]] = []
    span_rows: list[dict[str, Any]] = []
    reconstruction_mode = "artifact_only"
    if not args.no_reconstruct:
        reconstructed, preview_rows, span_rows = reconstruct_selected_prompts(
            selected,
            config_path=args.config,
            seed=args.seed,
            n=args.n,
            keep_rate=args.keep_rate,
        )
        reconstruction_mode = "bounded_compressor_only_reconstruction"

    summary, table, cases = analyze_retention(
        task77_cases,
        reconstructed_by_prompt=reconstructed,
        task77_artifacts_by_condition=artifacts,
    )
    summary.update(
        {
            "reconstruction_mode": reconstruction_mode,
            "compressor_loaded": not args.no_reconstruct,
            "target_model_loaded": False,
            "draft_model_loaded": False,
            "cuda_used": False,
            "generation_run": False,
            "summary_output": str(args.summary_output),
            "table_output": str(args.table_output),
            "cases_output": str(args.cases_output),
        }
    )
    if preview_rows:
        summary["reconstructed_output"] = str(args.reconstructed_output)
        _write_jsonl(args.reconstructed_output, preview_rows)
    if span_rows:
        summary["spans_output"] = str(args.spans_output)
        _write_jsonl(args.spans_output, span_rows)
    _write_json(args.summary_output, summary)
    _write_csv(args.table_output, table)
    _write_jsonl(args.cases_output, cases)
    print(json.dumps({
        "status": summary["status"],
        "reconstruction_mode": reconstruction_mode,
        "total_audited_cases": summary["total_audited_cases"],
        "count_by_evidence_retention_label": summary["count_by_evidence_retention_label"],
        "decisions": summary["decisions"],
        "summary_output": str(args.summary_output),
        "table_output": str(args.table_output),
        "cases_output": str(args.cases_output),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
