from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_system_build_and_evaluation.analysis.t47_quality_refinement import classify_row


ID_KEYS = ("sample_id", "id", "question_id", "fixture_id", "dataset_id")
INDEX_KEYS = ("dataset_index", "benchmark_prompt_index", "prompt_id")
EXPECTED_KEYS = ("expected_answer", "gold_answer", "reference_answer", "ground_truth_answer", "answer")
QUESTION_KEYS = ("question", "prompt", "input_text", "context", "original_prompt_preview", "final_prompt_preview")
COMPRESSED_TEXT_KEYS = ("compressed_prompt", "compressed_context")
COMPRESSED_PREVIEW_KEYS = (
    "compressed_prompt_preview",
    "compressed_context_preview",
    "final_prompt_preview",
    "final_prompt_tail_preview",
)
PROXY_KEYS = (
    "extracted_answer",
    "expected_extracted_answer",
    "extracted_answer_match",
    "numeric_correct",
    "numeric_match",
    "exact_match",
    "normalized_match",
    "normalized_text_match",
)
TAXONOMY_TAGS = (
    "answer_missing",
    "arithmetic_wrong",
    "format_or_extraction_issue",
    "truncation_or_cap_issue",
    "compressed_context_loss_possible",
    "generic_or_gibberish",
    "proxy_uncertain",
)
OUTCOME_GROUPS = (
    "both_correct",
    "large_correct_light_wrong",
    "large_wrong_light_correct",
    "both_wrong",
    "proxy_uncertain",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: line {line_number} is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: line {line_number} is not a JSON object")
        rows.append(payload)
    return rows


def _preview(value: Any, limit: int = 220) -> str:
    if not isinstance(value, str):
        return ""
    compact = " ".join(value.split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def _first_present(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _missing_fields(rows: list[dict[str, Any]]) -> list[str]:
    required = (
        "generated_text",
        "expected_answer",
        "fixture_id",
        "dataset_id",
        "prompt_id",
        "t_compress_ms",
        "R_actual",
        "tau_mean",
        "output_tokens",
        "compressor_profile",
        "compressor_path",
        "resolved_compressor_path",
        "local_files_only",
        "protected_suffix_preserved",
        "question_preserved",
    )
    present = {key for row in rows for key in row}
    return [key for key in required if key not in present]


def _schema_summary(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = sorted({key for row in rows for key in row})
    first = rows[0] if rows else {}
    return {
        "path": str(path),
        "row_count": len(rows),
        "sorted_keys": keys,
        "sample_id_like_fields": {key: first.get(key) for key in (*ID_KEYS, *INDEX_KEYS) if key in first},
        "prompt_question_fields_present": [key for key in QUESTION_KEYS if key in first],
        "gold_final_answer_fields_present": [key for key in EXPECTED_KEYS if key in first],
        "generated_text_field_present": "generated_text" in first,
        "compressed_prompt_context_fields_present": [
            key for key in (*COMPRESSED_TEXT_KEYS, *COMPRESSED_PREVIEW_KEYS) if key in first
        ],
        "numeric_exact_proxy_fields_present": [key for key in PROXY_KEYS if key in first],
        "missing_required_metadata_fields": _missing_fields(rows),
    }


def _unique_values(rows: list[dict[str, Any]], key: str) -> list[Any] | None:
    values = [row.get(key) for row in rows]
    if any(value in (None, "") for value in values):
        return None
    if len(set(values)) != len(values):
        return None
    return values


def _choose_pairing_key(large_rows: list[dict[str, Any]], light_rows: list[dict[str, Any]]) -> str | None:
    if len(large_rows) != len(light_rows):
        return None
    for key in ID_KEYS:
        large_values = _unique_values(large_rows, key)
        light_values = _unique_values(light_rows, key)
        if large_values is not None and set(large_values) == set(light_values):
            return key
    for key in INDEX_KEYS:
        large_values = _unique_values(large_rows, key)
        light_values = _unique_values(light_rows, key)
        if large_values is not None and set(large_values) == set(light_values):
            return key
    return None


def pair_rows(large_rows: list[dict[str, Any]], light_rows: list[dict[str, Any]]) -> dict[str, Any]:
    caveats: list[str] = []
    if len(large_rows) != len(light_rows):
        caveats.append(f"row_count_mismatch large={len(large_rows)} light={len(light_rows)}")

    key = _choose_pairing_key(large_rows, light_rows)
    pairs: list[dict[str, Any]] = []
    if key is not None:
        light_by_key = {row[key]: row for row in light_rows}
        for pair_index, large_row in enumerate(large_rows, start=1):
            sample_id = large_row[key]
            pairs.append(
                {
                    "pair_index": pair_index,
                    "sample_id": sample_id,
                    "pairing_key": key,
                    "large_row": large_row,
                    "light_row": light_by_key[sample_id],
                }
            )
        return {"pairing_method": key, "pairs": pairs, "caveats": caveats}

    row_count = min(len(large_rows), len(light_rows))
    caveats.append("paired_by_row_order_no_shared_unique_id_or_dataset_index")
    for index in range(row_count):
        pairs.append(
            {
                "pair_index": index + 1,
                "sample_id": index + 1,
                "pairing_key": "row_order",
                "large_row": large_rows[index],
                "light_row": light_rows[index],
            }
        )
    return {"pairing_method": "row_order", "pairs": pairs, "caveats": caveats}


def _existing_bool(row: dict[str, Any], keys: tuple[str, ...]) -> bool | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, bool):
            return value
    return None


def _score(row: dict[str, Any], *, row_index: int, condition: str, artifact: str) -> dict[str, Any]:
    expected = _first_present(row, EXPECTED_KEYS)
    generated = row.get("generated_text")
    missing_evaluation_fields = []
    if expected in (None, ""):
        missing_evaluation_fields.append("expected_answer")
    if not isinstance(generated, str) or not generated.strip():
        missing_evaluation_fields.append("generated_text")

    classified = classify_row(row, row_index=row_index, condition=condition, artifact=artifact)
    existing_numeric = _existing_bool(row, ("numeric_correct", "extracted_answer_match", "numeric_match"))
    existing_exact = _existing_bool(row, ("exact_match", "normalized_match", "normalized_text_match"))
    computed_numeric = bool(classified.get("numeric_match"))
    numeric_correct = existing_numeric if existing_numeric is not None else computed_numeric
    exact_contains = existing_exact if existing_exact is not None else bool(
        classified.get("exact_match") or classified.get("normalized_text_match")
    )

    return {
        "expected_answer": str(expected) if expected is not None else "",
        "expected_numeric": classified.get("expected_numeric"),
        "generated_text": generated if isinstance(generated, str) else "",
        "extracted_answer": row.get("extracted_answer", classified.get("extracted_answer")),
        "candidate_answers": classified.get("candidate_answers", []),
        "extraction_source": classified.get("extraction_source"),
        "numeric_correct": numeric_correct,
        "numeric_correct_source": "artifact_field" if existing_numeric is not None else "computed_t47_extractor",
        "exact_contains": exact_contains,
        "exact_contains_source": "artifact_field" if existing_exact is not None else "computed_text_containment",
        "proxy_uncertain": bool(missing_evaluation_fields or classified.get("failure_type") == "parse_ambiguous"),
        "missing_evaluation_fields": missing_evaluation_fields,
        "failure_type": classified.get("failure_type"),
        "truncated_or_stopped_early": bool(classified.get("truncated_or_stopped_early")),
    }


def _is_generic_or_gibberish(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    words = stripped.split()
    if len(words) < 4:
        return True
    lowered = stripped.lower()
    generic_phrases = ("i cannot", "as an ai", "not enough information", "unable to determine")
    return any(phrase in lowered for phrase in generic_phrases)


def _taxonomy_for_large_pass_light_fail(light_score: dict[str, Any], light_row: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    generated_text = light_score["generated_text"]
    if light_score["proxy_uncertain"]:
        tags.append("proxy_uncertain")
    if not light_score.get("extracted_answer"):
        tags.append("answer_missing")
    elif light_score.get("exact_contains") and not light_score.get("numeric_correct"):
        tags.append("format_or_extraction_issue")
    elif light_score.get("numeric_correct") is False:
        tags.append("arithmetic_wrong")
    if light_score.get("truncated_or_stopped_early"):
        tags.append("truncation_or_cap_issue")
    if _is_generic_or_gibberish(generated_text):
        tags.append("generic_or_gibberish")
    if any(light_row.get(key) for key in COMPRESSED_TEXT_KEYS) and (
        "answer_missing" in tags or "arithmetic_wrong" in tags
    ):
        tags.append("compressed_context_loss_possible")
    if not tags:
        tags.append("proxy_uncertain")
    return sorted(set(tags), key=TAXONOMY_TAGS.index)


def _outcome_group(large_score: dict[str, Any], light_score: dict[str, Any]) -> str:
    if large_score["proxy_uncertain"] or light_score["proxy_uncertain"]:
        return "proxy_uncertain"
    large_correct = bool(large_score["numeric_correct"])
    light_correct = bool(light_score["numeric_correct"])
    if large_correct and light_correct:
        return "both_correct"
    if large_correct and not light_correct:
        return "large_correct_light_wrong"
    if not large_correct and light_correct:
        return "large_wrong_light_correct"
    return "both_wrong"


def _metadata_checks(large_row: dict[str, Any], light_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "large_compressor_profile": large_row.get("compressor_profile"),
        "light_compressor_profile": light_row.get("compressor_profile"),
        "large_local_files_only": large_row.get("local_files_only"),
        "light_local_files_only": light_row.get("local_files_only"),
        "large_compressor_path_present": bool(large_row.get("compressor_path")),
        "light_compressor_path_present": bool(light_row.get("compressor_path")),
        "large_resolved_compressor_path_present": bool(large_row.get("resolved_compressor_path")),
        "light_resolved_compressor_path_present": bool(light_row.get("resolved_compressor_path")),
        "large_question_preserved": large_row.get("question_preserved"),
        "light_question_preserved": light_row.get("question_preserved"),
        "large_protected_suffix_preserved": large_row.get("protected_suffix_preserved"),
        "light_protected_suffix_preserved": light_row.get("protected_suffix_preserved"),
    }


def _paired_audit_rows(paired: dict[str, Any], *, large_artifact: Path, light_artifact: Path) -> list[dict[str, Any]]:
    audit_rows: list[dict[str, Any]] = []
    for pair in paired["pairs"]:
        large_row = pair["large_row"]
        light_row = pair["light_row"]
        pair_index = pair["pair_index"]
        large_score = _score(large_row, row_index=pair_index, condition="large", artifact=str(large_artifact))
        light_score = _score(light_row, row_index=pair_index, condition="light", artifact=str(light_artifact))
        group = _outcome_group(large_score, light_score)
        taxonomy_tags = (
            _taxonomy_for_large_pass_light_fail(light_score, light_row)
            if group == "large_correct_light_wrong"
            else []
        )
        audit_rows.append(
            {
                "pair_index": pair_index,
                "sample_id": pair["sample_id"],
                "pairing_key": pair["pairing_key"],
                "question_prompt_preview": _preview(_first_present(large_row, QUESTION_KEYS)),
                "gold_answer": large_score["expected_answer"] or light_score["expected_answer"],
                "large_generated_text": large_score["generated_text"],
                "light_generated_text": light_score["generated_text"],
                "large_generated_preview": _preview(large_score["generated_text"]),
                "light_generated_preview": _preview(light_score["generated_text"]),
                "large_extracted_numeric_answer": large_score["extracted_answer"],
                "light_extracted_numeric_answer": light_score["extracted_answer"],
                "large_numeric_correct": large_score["numeric_correct"],
                "light_numeric_correct": light_score["numeric_correct"],
                "large_exact_contains": large_score["exact_contains"],
                "light_exact_contains": light_score["exact_contains"],
                "large_extraction_source": large_score["extraction_source"],
                "light_extraction_source": light_score["extraction_source"],
                "large_failure_type": large_score["failure_type"],
                "light_failure_type": light_score["failure_type"],
                "outcome_group": group,
                "failure_taxonomy_tags": taxonomy_tags,
                "large_t_compress_ms": large_row.get("t_compress_ms"),
                "light_t_compress_ms": light_row.get("t_compress_ms"),
                "large_R_actual": large_row.get("R_actual", large_row.get("actual_compression_ratio")),
                "light_R_actual": light_row.get("R_actual", light_row.get("actual_compression_ratio")),
                "large_tau_mean": large_row.get("tau_mean"),
                "light_tau_mean": light_row.get("tau_mean"),
                "large_output_length": large_row.get("output_tokens", large_row.get("generated_token_count")),
                "light_output_length": light_row.get("output_tokens", light_row.get("generated_token_count")),
                "large_missing_evaluation_fields": large_score["missing_evaluation_fields"],
                "light_missing_evaluation_fields": light_score["missing_evaluation_fields"],
                "large_compressed_prompt_preview": _preview(large_row.get("compressed_prompt_preview")),
                "light_compressed_prompt_preview": _preview(light_row.get("compressed_prompt_preview")),
                "large_final_prompt_tail_preview": _preview(large_row.get("final_prompt_tail_preview")),
                "light_final_prompt_tail_preview": _preview(light_row.get("final_prompt_tail_preview")),
                "compressor_metadata_checks": _metadata_checks(large_row, light_row),
            }
        )
    return audit_rows


def build_recommendation(
    *,
    outcome_group_counts: dict[str, int],
    failure_taxonomy_counts: dict[str, int],
    has_compressed_prompt_text: bool,
) -> dict[str, Any]:
    proxy_uncertain = outcome_group_counts.get("proxy_uncertain", 0)
    extraction_issues = failure_taxonomy_counts.get("format_or_extraction_issue", 0)
    answer_missing = failure_taxonomy_counts.get("answer_missing", 0)
    arithmetic_wrong = failure_taxonomy_counts.get("arithmetic_wrong", 0)
    compression_possible = failure_taxonomy_counts.get("compressed_context_loss_possible", 0)

    if proxy_uncertain or extraction_issues:
        next_task = "T95B"
        rationale = (
            "Proceed to T95B Quality Proxy Calibration because proxy uncertainty or format/extraction sensitivity "
            "is present in the row audit."
        )
    elif compression_possible or (arithmetic_wrong + answer_missing > 0 and has_compressed_prompt_text):
        next_task = "T95C"
        rationale = (
            "Proceed to T95C Light Compressor Parameter/Tail Policy Triage because the loss looks like real output "
            "quality degradation with compressed-prompt evidence available for tuning."
        )
    else:
        next_task = "BOUNDED_SAMPLE_CHECK"
        rationale = (
            "Use an additional bounded sample check only after T95B/T95C reasoning, because current rows do not give "
            "a clear proxy or compressor diagnosis."
        )

    return {
        "next_task": next_task,
        "t95b_needed": next_task == "T95B",
        "t95c_needed": next_task == "T95C",
        "n30_recommended_now": False,
        "rationale": rationale,
        "claim_boundary": {
            "deterministic_proxy_analysis_only": True,
            "no_model_inference": True,
            "no_benchmark_run": True,
            "no_final_quality_claim": True,
            "no_final_speedup_claim": True,
            "no_deployment_or_8gb_claim": True,
            "no_qmsum_semantic_correctness_claim": True,
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "pair_index",
        "sample_id",
        "outcome_group",
        "gold_answer",
        "large_extracted_numeric_answer",
        "light_extracted_numeric_answer",
        "large_numeric_correct",
        "light_numeric_correct",
        "large_exact_contains",
        "light_exact_contains",
        "failure_taxonomy_tags",
        "large_t_compress_ms",
        "light_t_compress_ms",
        "large_R_actual",
        "light_R_actual",
        "large_tau_mean",
        "light_tau_mean",
        "large_output_length",
        "light_output_length",
        "large_generated_preview",
        "light_generated_preview",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            csv_row = {field: row.get(field) for field in fieldnames}
            csv_row["failure_taxonomy_tags"] = "|".join(row.get("failure_taxonomy_tags", []))
            writer.writerow(csv_row)


def analyze(large_artifact: Path, light_artifact: Path, output_dir: Path | None = None) -> dict[str, Any]:
    large_rows = load_jsonl(large_artifact)
    light_rows = load_jsonl(light_artifact)
    paired = pair_rows(large_rows, light_rows)
    audit_rows = _paired_audit_rows(paired, large_artifact=large_artifact, light_artifact=light_artifact)

    outcome_counts = {group: 0 for group in OUTCOME_GROUPS}
    outcome_counts.update(Counter(row["outcome_group"] for row in audit_rows))
    taxonomy_counts = {tag: 0 for tag in TAXONOMY_TAGS}
    taxonomy_counts.update(Counter(tag for row in audit_rows for tag in row["failure_taxonomy_tags"]))
    has_compressed_prompt_text = any(
        any(row.get(key) for key in COMPRESSED_TEXT_KEYS) for row in (*large_rows, *light_rows)
    )
    recommendation = build_recommendation(
        outcome_group_counts=outcome_counts,
        failure_taxonomy_counts=taxonomy_counts,
        has_compressed_prompt_text=has_compressed_prompt_text,
    )
    summary = {
        "task": "Task95A",
        "title": "Analysis and Failure Row Audit",
        "inputs": {
            "large_artifact": str(large_artifact),
            "light_artifact": str(light_artifact),
        },
        "method": {
            "analysis_only": True,
            "model_loading": False,
            "benchmark_run": False,
            "judge": "deterministic_only_no_llm_judge",
            "extractor": "scripts.phase_1_system_build_and_evaluation.analysis.t47_quality_refinement.classify_row",
            "pairing_method": paired["pairing_method"],
            "pairing_caveats": paired["caveats"],
            "compressed_prompt_text_available": has_compressed_prompt_text,
            "compressed_prompt_previews_available": any(
                any(row.get(key) for key in COMPRESSED_PREVIEW_KEYS) for row in (*large_rows, *light_rows)
            ),
        },
        "schemas": {
            "large": _schema_summary(large_artifact, large_rows),
            "light": _schema_summary(light_artifact, light_rows),
        },
        "missing_metadata": {
            "large": _missing_fields(large_rows),
            "light": _missing_fields(light_rows),
        },
        "row_count": {
            "large": len(large_rows),
            "light": len(light_rows),
            "paired": len(audit_rows),
        },
        "outcome_group_counts": outcome_counts,
        "failure_taxonomy_counts": taxonomy_counts,
        "large_correct_light_wrong_examples": [
            {
                "pair_index": row["pair_index"],
                "sample_id": row["sample_id"],
                "gold_answer": row["gold_answer"],
                "light_extracted_numeric_answer": row["light_extracted_numeric_answer"],
                "failure_taxonomy_tags": row["failure_taxonomy_tags"],
                "light_generated_preview": row["light_generated_preview"],
            }
            for row in audit_rows
            if row["outcome_group"] == "large_correct_light_wrong"
        ],
        "recommendation": recommendation,
        "claim_boundary": recommendation["claim_boundary"],
    }

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(output_dir / "task95a_failure_row_pairs.jsonl", audit_rows)
        _write_json(output_dir / "task95a_failure_taxonomy_summary.json", summary)
        _write_csv(output_dir / "task95a_large_vs_light_row_table.csv", audit_rows)
        _write_json(output_dir / "task95a_recommendation.json", recommendation)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Task95A deterministic large-vs-light failure row audit")
    parser.add_argument("--large-jsonl", type=Path, required=True, help="Task94 large compressor JSONL artifact")
    parser.add_argument("--light-jsonl", type=Path, required=True, help="Task94 light compressor JSONL artifact")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for Task95A audit artifacts")
    args = parser.parse_args()

    summary = analyze(args.large_jsonl, args.light_jsonl, args.output_dir)
    print(f"task={summary['task']}")
    print(f"pairing_method={summary['method']['pairing_method']}")
    print(f"outcome_group_counts={summary['outcome_group_counts']}")
    print(f"failure_taxonomy_counts={summary['failure_taxonomy_counts']}")
    print(f"recommendation={summary['recommendation']['next_task']}")
    print(f"wrote={args.output_dir}")


if __name__ == "__main__":
    main()
