from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_analysis.analyze_task47_quality_refinement import classify_row, extract_numeric_answer, normalize_numeric


ARTIFACTS = {
    "Baseline-AR": Path("results/task56_gsm8k_short_baseline_ar_n10_mnt192.jsonl"),
    "DFlash-R1": Path("results/task56_gsm8k_short_dflash_r1_n10_mnt192.jsonl"),
    "LLMLingua-AR-R2": Path("results/task56_gsm8k_short_llmlingua_ar_r2_n10_mnt192.jsonl"),
    "CC-DFlash-R2": Path("results/task56_gsm8k_short_cc_dflash_r2_n10_mnt192.jsonl"),
}
DATASET = Path("data/eval/gsm8k_100.jsonl")
DEFAULT_OUTPUT = Path("results/task57_compressed_preview_triage_summary.json")
DEFAULT_SAMPLES_OUTPUT = Path("results/task57_compressed_preview_failure_samples.jsonl")
COMPRESSED_CONDITIONS = ["LLMLingua-AR-R2", "CC-DFlash-R2"]
UNCOMPRESSED_CONDITIONS = ["Baseline-AR", "DFlash-R1"]
METADATA_FIELDS = [
    "keep_rate",
    "t_compress_ms",
    "original_input_tokens",
    "compressed_input_tokens",
    "compression_ratio",
    "actual_compression_ratio",
    "original_context_preview",
    "compressed_context_preview",
    "original_prompt_preview",
    "compressed_prompt_preview",
    "question_preserved",
]
NUMBER_RE = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?")
FINAL_ANSWER_INSTRUCTION_RE = re.compile(
    r"final\s+(?:numeric\s+)?answer|end\s+with\s+exactly\s+one\s+line|Final answer:\s*<number>",
    re.IGNORECASE,
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: line {line_number} is not valid JSON ({exc})") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}: line {line_number} is not a JSON object")
        rows.append(row)
    return rows


def compact(text: str | None, limit: int = 360) -> str:
    if not isinstance(text, str):
        return ""
    collapsed = " ".join(text.split())
    return collapsed[:limit] + ("..." if len(collapsed) > limit else "")


def tail(text: str | None, limit: int = 260) -> str:
    if not isinstance(text, str):
        return ""
    collapsed = " ".join(text.split())
    return ("..." if len(collapsed) > limit else "") + collapsed[-limit:]


def normalized_numbers(text: str | None) -> list[str]:
    if not isinstance(text, str):
        return []
    values: list[str] = []
    seen: set[str] = set()
    for match in NUMBER_RE.finditer(text):
        normalized = normalize_numeric(match.group(0))
        if normalized is not None and normalized not in seen:
            seen.add(normalized)
            values.append(normalized)
    return values


def contains_number(text: str | None, number: str) -> bool:
    if not isinstance(text, str) or not number:
        return False
    return number in normalized_numbers(text)


def hit_max_tokens(row: dict[str, Any]) -> bool:
    output_tokens = row.get("output_tokens")
    max_new_tokens = row.get("max_new_tokens")
    return isinstance(output_tokens, (int, float)) and isinstance(max_new_tokens, (int, float)) and output_tokens >= max_new_tokens


def has_final_answer_instruction(text: str | None) -> bool:
    return isinstance(text, str) and bool(FINAL_ANSWER_INSTRUCTION_RE.search(text))


def metadata_presence(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing_by_field = {
        field: sum(1 for row in rows if field not in row or row.get(field) is None)
        for field in METADATA_FIELDS
    }
    complete_rows = sum(1 for row in rows if all(field in row and row.get(field) is not None for field in METADATA_FIELDS))
    return {
        "fields": METADATA_FIELDS,
        "rows": len(rows),
        "complete_rows": complete_rows,
        "complete_rate": complete_rows / len(rows) if rows else 0.0,
        "missing_by_field": missing_by_field,
        "all_questions_preserved": all(row.get("question_preserved") is True for row in rows),
    }


def success(classified: dict[str, Any]) -> bool:
    return bool(classified.get("numeric_match"))


def label_failure(
    *,
    compressed_classified: dict[str, Any],
    compressed_row: dict[str, Any],
    uncompressed_success: bool,
    uncompressed_all_fail: bool,
    final_instruction_in_compressed_preview: bool,
    missing_key_numbers: list[str],
    preview_likely_truncated: bool,
) -> str:
    if success(compressed_classified):
        return "PASS_MATCH"
    if uncompressed_all_fail:
        return "MODEL_FAIL_SHARED"
    if uncompressed_success and missing_key_numbers and not preview_likely_truncated:
        return "COMPRESSION_REMOVED_CRITICAL_INFO"
    if not final_instruction_in_compressed_preview:
        return "FINAL_ANSWER_INSTRUCTION_LOST_OR_WEAKENED"
    if hit_max_tokens(compressed_row):
        return "TRUNCATION_DESPITE_POLICY"
    if compressed_classified.get("exact_match") and not compressed_classified.get("numeric_match"):
        return "EXTRACTION_MISS"
    return "UNCLEAR"


def analyze() -> dict[str, Any]:
    dataset_rows = {str(row["id"]): row for row in load_jsonl(DATASET)}
    rows_by_condition = {condition: load_jsonl(path) for condition, path in ARTIFACTS.items()}

    classified_by_condition: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for condition, rows in rows_by_condition.items():
        for row_index, row in enumerate(rows, start=1):
            dataset_id = str(row.get("dataset_id") or row.get("fixture_id") or row.get("prompt_id"))
            classified_by_condition[condition][dataset_id] = {
                "row": row,
                "classified": classify_row(
                    row,
                    row_index=row_index,
                    condition=condition,
                    artifact=str(ARTIFACTS[condition]),
                ),
            }

    metadata = {
        condition: metadata_presence(rows_by_condition[condition])
        for condition in COMPRESSED_CONDITIONS
    }

    final_instruction_survival: dict[str, dict[str, Any]] = {}
    for condition in COMPRESSED_CONDITIONS:
        rows = rows_by_condition[condition]
        compressed_preview_count = sum(1 for row in rows if has_final_answer_instruction(row.get("compressed_prompt_preview")))
        original_preview_count = sum(1 for row in rows if has_final_answer_instruction(row.get("original_prompt_preview")))
        final_instruction_survival[condition] = {
            "rows": len(rows),
            "compressed_prompt_preview_has_instruction": compressed_preview_count,
            "original_prompt_preview_has_instruction": original_preview_count,
            "compressed_prompt_preview_has_instruction_rate": compressed_preview_count / len(rows) if rows else 0.0,
            "original_prompt_preview_has_instruction_rate": original_preview_count / len(rows) if rows else 0.0,
            "note": (
                "Stored previews are prefix previews; absence does not prove the full prompt lacks the instruction, "
                "but Task 56 compressed preview metadata does not show the strict final-answer policy."
            ),
        }

    records: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()
    failure_label_counts: Counter[str] = Counter()
    counts_by_condition: dict[str, Counter[str]] = defaultdict(Counter)
    compression_evidence_counts: Counter[str] = Counter()

    dataset_ids = sorted(set().union(*(set(items.keys()) for items in classified_by_condition.values())))
    for dataset_id in dataset_ids:
        dataset_row = dataset_rows.get(dataset_id, {})
        question_text = str(dataset_row.get("question") or "")
        context_text = str(dataset_row.get("context") or "")
        key_numbers = normalized_numbers(f"{context_text}\n{question_text}")
        uncompressed = {
            condition: classified_by_condition[condition][dataset_id]
            for condition in UNCOMPRESSED_CONDITIONS
            if dataset_id in classified_by_condition[condition]
        }
        uncompressed_success = any(success(item["classified"]) for item in uncompressed.values())
        uncompressed_all_fail = bool(uncompressed) and all(not success(item["classified"]) for item in uncompressed.values())

        for condition in COMPRESSED_CONDITIONS:
            if dataset_id not in classified_by_condition[condition]:
                continue
            item = classified_by_condition[condition][dataset_id]
            row = item["row"]
            classified = item["classified"]
            compressed_preview = str(row.get("compressed_prompt_preview") or "")
            original_preview = str(row.get("original_prompt_preview") or "")
            final_instruction_in_compressed_preview = has_final_answer_instruction(compressed_preview)
            final_instruction_in_original_preview = has_final_answer_instruction(original_preview)
            missing_key_numbers = [number for number in key_numbers if not contains_number(compressed_preview, number)]
            preview_likely_truncated = compressed_preview.endswith("...") or original_preview.endswith("...")
            label = label_failure(
                compressed_classified=classified,
                compressed_row=row,
                uncompressed_success=uncompressed_success,
                uncompressed_all_fail=uncompressed_all_fail,
                final_instruction_in_compressed_preview=final_instruction_in_compressed_preview,
                missing_key_numbers=missing_key_numbers,
                preview_likely_truncated=preview_likely_truncated,
            )
            label_counts[label] += 1
            counts_by_condition[condition][label] += 1
            if label != "PASS_MATCH":
                failure_label_counts[label] += 1

            critical_info_directly_missing = bool(missing_key_numbers) and not preview_likely_truncated
            if critical_info_directly_missing:
                compression_evidence_counts["critical_numbers_missing_in_complete_preview"] += 1
            elif missing_key_numbers:
                compression_evidence_counts["critical_number_status_unclear_due_prefix_preview"] += 1
            else:
                compression_evidence_counts["visible_numeric_tokens_preserved_in_preview"] += 1

            extraction = extract_numeric_answer(row.get("generated_text"))
            record = {
                "dataset_id": dataset_id,
                "condition": condition,
                "prompt_id": row.get("prompt_id"),
                "expected_answer": row.get("expected_answer") or dataset_row.get("expected_answer"),
                "expected_numeric": normalize_numeric(row.get("expected_answer") or dataset_row.get("expected_answer")),
                "extracted_answer": extraction.answer,
                "extraction_source": extraction.source,
                "numeric_match": classified.get("numeric_match"),
                "exact_match": classified.get("exact_match"),
                "failure_type": classified.get("failure_type"),
                "triage_label": label,
                "output_tokens": row.get("output_tokens"),
                "max_new_tokens": row.get("max_new_tokens"),
                "hit_max_new_tokens": hit_max_tokens(row),
                "uncompressed_success": uncompressed_success,
                "uncompressed_all_fail": uncompressed_all_fail,
                "uncompressed_numeric_matches": {
                    name: bool(data["classified"].get("numeric_match"))
                    for name, data in sorted(uncompressed.items())
                },
                "final_instruction_in_original_preview": final_instruction_in_original_preview,
                "final_instruction_in_compressed_preview": final_instruction_in_compressed_preview,
                "preview_likely_truncated": preview_likely_truncated,
                "key_numbers": key_numbers,
                "missing_key_numbers_in_compressed_preview": missing_key_numbers,
                "critical_info_directly_missing_from_preview": critical_info_directly_missing,
                "question_preserved": row.get("question_preserved"),
                "keep_rate": row.get("keep_rate"),
                "t_compress_ms": row.get("t_compress_ms"),
                "original_input_tokens": row.get("original_input_tokens"),
                "compressed_input_tokens": row.get("compressed_input_tokens"),
                "compression_ratio": row.get("compression_ratio") or row.get("actual_compression_ratio") or row.get("R_actual"),
                "original_context_preview": compact(row.get("original_context_preview")),
                "compressed_context_preview": compact(row.get("compressed_context_preview")),
                "original_prompt_preview": compact(row.get("original_prompt_preview")),
                "compressed_prompt_preview": compact(row.get("compressed_prompt_preview")),
                "generated_text_tail": tail(row.get("generated_text")),
            }
            records.append(record)

    failures = [record for record in records if record["triage_label"] != "PASS_MATCH"]
    representative: list[dict[str, Any]] = []
    seen_examples: set[tuple[str, str]] = set()
    for condition in COMPRESSED_CONDITIONS:
        condition_failures = [
            record
            for record in failures
            if record["condition"] == condition
            and record["triage_label"] == "FINAL_ANSWER_INSTRUCTION_LOST_OR_WEAKENED"
        ]
        for record in condition_failures[:2]:
            representative.append(record)
            seen_examples.add((record["condition"], record["dataset_id"]))
    for record in failures:
        key = (record["condition"], record["dataset_id"])
        if key in seen_examples:
            continue
        representative.append(record)
        seen_examples.add(key)
        if len(representative) >= 5:
            break

    uncompressed_pass_compressed_fail = [
        record
        for record in records
        if record["triage_label"] != "PASS_MATCH" and record["uncompressed_success"]
    ]
    compressed_rows = len(records)
    compressed_failures = len(failures)

    return {
        "task": "Task 57 compressed GSM8K preview triage",
        "status": "PASS",
        "claim_policy": "read-only preview triage; no final correctness claim and no new benchmark run",
        "inputs": {
            "artifacts": {condition: str(path) for condition, path in ARTIFACTS.items()},
            "dataset": str(DATASET),
        },
        "metadata_presence": metadata,
        "final_answer_instruction_survival": final_instruction_survival,
        "label_counts": dict(sorted(label_counts.items())),
        "failure_label_counts": dict(sorted(failure_label_counts.items())),
        "label_counts_by_condition": {
            condition: dict(sorted(counter.items()))
            for condition, counter in sorted(counts_by_condition.items())
        },
        "compression_preview_evidence_counts": dict(sorted(compression_evidence_counts.items())),
        "summary": {
            "compressed_rows": compressed_rows,
            "compressed_failures": compressed_failures,
            "compressed_numeric_matches": label_counts.get("PASS_MATCH", 0),
            "uncompressed_pass_compressed_fail_rows": len(uncompressed_pass_compressed_fail),
            "final_instruction_seen_in_any_compressed_preview": any(
                item["compressed_prompt_preview_has_instruction"] > 0
                for item in final_instruction_survival.values()
            ),
            "direct_compression_loss_supported_by_complete_preview": (
                compression_evidence_counts.get("critical_numbers_missing_in_complete_preview", 0) > 0
            ),
            "preview_limit_caveat": (
                "Most prompt previews are prefix-capped, so missing tail instructions or tail numbers should be "
                "treated as insufficient preview evidence unless the preview is complete."
            ),
            "recommendation": (
                "Fix/protect the GSM8K final-answer instruction outside compression before larger n; inspect full "
                "or tail prompt previews before claiming compression removes critical numbers."
            ),
        },
        "records": records,
        "representative_failures": representative,
    }


def write_samples(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 56 compressed GSM8K prompt-preview failures")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--samples-output", default=str(DEFAULT_SAMPLES_OUTPUT))
    args = parser.parse_args()

    summary = analyze()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_samples(summary["representative_failures"], Path(args.samples_output))

    print(f"status={summary['status']}")
    print(f"compressed_rows={summary['summary']['compressed_rows']}")
    print(f"compressed_failures={summary['summary']['compressed_failures']}")
    print(f"label_counts={summary['label_counts']}")
    print(f"failure_label_counts={summary['failure_label_counts']}")
    for condition, metadata in sorted(summary["metadata_presence"].items()):
        print(
            f"metadata {condition}: complete={metadata['complete_rows']}/{metadata['rows']} "
            f"question_preserved={metadata['all_questions_preserved']}"
        )
    for condition, survival in sorted(summary["final_answer_instruction_survival"].items()):
        print(
            f"final_instruction {condition}: compressed_preview="
            f"{survival['compressed_prompt_preview_has_instruction']}/{survival['rows']} "
            f"original_preview={survival['original_prompt_preview_has_instruction']}/{survival['rows']}"
        )


if __name__ == "__main__":
    main()
