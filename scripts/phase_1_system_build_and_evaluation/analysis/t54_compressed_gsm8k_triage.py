from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_system_build_and_evaluation.analysis.t47_quality_refinement import classify_row, extract_numeric_answer


ARTIFACTS = {
    "Baseline-AR": Path("results/phase_1_system_build_and_evaluation/early_experiments/task53_gsm8k_short_baseline_ar_n10_mnt128.jsonl"),
    "DFlash-R1": Path("results/phase_1_system_build_and_evaluation/early_experiments/task53_gsm8k_short_dflash_r1_n10_mnt128.jsonl"),
    "LLMLingua-AR-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task53_gsm8k_short_llmlingua_ar_r2_n10_mnt128.jsonl"),
    "CC-DFlash-R2": Path("results/phase_1_system_build_and_evaluation/early_experiments/task53_gsm8k_short_cc_dflash_r2_n10_mnt128.jsonl"),
}
DATASET = Path("data/eval/gsm8k_100.jsonl")
DEFAULT_JSON_OUTPUT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task54_compressed_gsm8k_failure_triage.json")
DEFAULT_SAMPLES_OUTPUT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task54_compressed_gsm8k_failure_samples.jsonl")
COMPRESSED_CONDITIONS = {"LLMLingua-AR-R2", "CC-DFlash-R2"}
UNCOMPRESSED_CONDITIONS = {"Baseline-AR", "DFlash-R1"}


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


def excerpt(text: str | None, limit: int = 360) -> str:
    if not isinstance(text, str):
        return ""
    compact = " ".join(text.split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def tail_excerpt(text: str | None, limit: int = 240) -> str:
    if not isinstance(text, str):
        return ""
    compact = " ".join(text.split())
    return ("..." if len(compact) > limit else "") + compact[-limit:]


def hit_max_tokens(row: dict[str, Any]) -> bool:
    output_tokens = row.get("output_tokens")
    max_new_tokens = row.get("max_new_tokens")
    return isinstance(output_tokens, (int, float)) and isinstance(max_new_tokens, (int, float)) and output_tokens >= max_new_tokens


def has_final_answer_marker(text: str | None) -> bool:
    if not isinstance(text, str):
        return False
    lowered = text.lower()
    return "final answer" in lowered or "answer:" in lowered or "####" in lowered


def success(classified: dict[str, Any]) -> bool:
    # Numeric extraction is the primary GSM8K quality proxy. Exact containment is
    # retained as a diagnostic because short answers can appear as unrelated
    # intermediate numbers in the reasoning text.
    return bool(classified.get("numeric_match"))


def primary_label(
    *,
    condition: str,
    classified: dict[str, Any],
    row: dict[str, Any],
    prompt_group: dict[str, dict[str, Any]],
) -> str:
    if success(classified):
        return "PASS_MATCH"

    generated_text = row.get("generated_text")
    hit_cap = hit_max_tokens(row)
    marker = has_final_answer_marker(generated_text)
    extraction_source = classified.get("extraction_source")
    extracted = classified.get("extracted_answer")

    uncompressed_success = any(
        success(prompt_group[name]["classified"])
        for name in UNCOMPRESSED_CONDITIONS
        if name in prompt_group
    )
    uncompressed_all_fail = all(
        not success(prompt_group[name]["classified"])
        for name in UNCOMPRESSED_CONDITIONS
        if name in prompt_group
    )

    if condition in UNCOMPRESSED_CONDITIONS and uncompressed_all_fail:
        return "MODEL_FAIL_UNCOMPRESSED"

    if condition in COMPRESSED_CONDITIONS and uncompressed_success:
        return "COMPRESSION_LOSS_LIKELY"

    if hit_cap and not marker:
        return "TRUNCATION_LIKELY"

    if extracted is not None and extraction_source in {"last_number_fallback", "marked_final_answer"}:
        return "FORMAT/PROMPT_ISSUE"

    if classified.get("normalized_text_match") and not classified.get("numeric_match"):
        return "EXTRACTION_MISS"

    return "UNCLEAR"


def analyze() -> dict[str, Any]:
    dataset_rows = {row["id"]: row for row in load_jsonl(DATASET)}
    rows_by_condition = {condition: load_jsonl(path) for condition, path in ARTIFACTS.items()}

    by_prompt: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    condition_summaries: dict[str, dict[str, Any]] = {}

    for condition, rows in rows_by_condition.items():
        label_counts: Counter[str] = Counter()
        failure_type_counts: Counter[str] = Counter()
        exact = numeric = hit_cap_count = generated_present = 0
        for index, row in enumerate(rows, start=1):
            fixture_id = row.get("fixture_id") or row.get("dataset_id") or str(row.get("prompt_id"))
            classified = classify_row(row, row_index=index, condition=condition, artifact=str(ARTIFACTS[condition]))
            exact += int(bool(classified.get("exact_match")))
            numeric += int(bool(classified.get("numeric_match")))
            hit_cap_count += int(hit_max_tokens(row))
            generated_present += int(isinstance(row.get("generated_text"), str) and bool(row["generated_text"].strip()))
            failure_type_counts[str(classified.get("failure_type"))] += 1
            by_prompt[str(fixture_id)][condition] = {
                "row": row,
                "classified": classified,
                "dataset_row": dataset_rows.get(str(fixture_id), {}),
            }
        condition_summaries[condition] = {
            "artifact": str(ARTIFACTS[condition]),
            "rows": len(rows),
            "exact_match_count": exact,
            "numeric_match_count": numeric,
            "hit_max_new_tokens_count": hit_cap_count,
            "generated_text_present_count": generated_present,
            "avg_output_tokens": sum(float(r.get("output_tokens", 0.0)) for r in rows) / len(rows) if rows else 0.0,
            "avg_generation_time_s": sum(float(r.get("generation_time_s", 0.0)) for r in rows) / len(rows) if rows else 0.0,
            "avg_t_compress_ms": (
                sum(float(r.get("t_compress_ms", 0.0)) for r in rows) / len(rows) if rows else 0.0
            ),
            "failure_type_counts": dict(sorted(failure_type_counts.items())),
            "label_counts": dict(label_counts),
        }

    rows: list[dict[str, Any]] = []
    label_counts: Counter[str] = Counter()
    label_counts_by_condition: dict[str, Counter[str]] = defaultdict(Counter)
    per_prompt: list[dict[str, Any]] = []

    for fixture_id, prompt_group in sorted(by_prompt.items()):
        dataset_row = next((entry.get("dataset_row", {}) for entry in prompt_group.values() if entry.get("dataset_row")), {})
        prompt_record = {
            "fixture_id": fixture_id,
            "question": dataset_row.get("question", ""),
            "expected_answer": dataset_row.get("expected_answer")
            or next((entry["row"].get("expected_answer") for entry in prompt_group.values()), ""),
            "conditions": {},
        }
        for condition in ARTIFACTS:
            if condition not in prompt_group:
                continue
            row = prompt_group[condition]["row"]
            classified = prompt_group[condition]["classified"]
            extraction = extract_numeric_answer(row.get("generated_text"))
            label = primary_label(
                condition=condition,
                classified=classified,
                row=row,
                prompt_group=prompt_group,
            )
            label_counts[label] += 1
            label_counts_by_condition[condition][label] += 1
            record = {
                "fixture_id": fixture_id,
                "prompt_id": row.get("prompt_id"),
                "condition": condition,
                "expected_answer": prompt_record["expected_answer"],
                "extracted_answer": extraction.answer,
                "candidate_answers": extraction.candidates,
                "extraction_source": extraction.source,
                "exact_match": classified.get("exact_match"),
                "numeric_match": classified.get("numeric_match"),
                "failure_type": classified.get("failure_type"),
                "triage_label": label,
                "hit_max_new_tokens": hit_max_tokens(row),
                "output_tokens": row.get("output_tokens"),
                "max_new_tokens": row.get("max_new_tokens"),
                "question_preserved": row.get("question_preserved"),
                "R_actual": row.get("R_actual"),
                "N_original": row.get("N_original"),
                "N_compressed": row.get("N_compressed"),
                "compressed_prompt_available": any(
                    field in row for field in ("compressed_text", "compressed_prompt", "prompt_text", "prompt")
                ),
                "generated_text_excerpt": excerpt(row.get("generated_text")),
                "generated_text_tail": tail_excerpt(row.get("generated_text")),
            }
            rows.append(record)
            prompt_record["conditions"][condition] = {
                "triage_label": label,
                "exact_match": classified.get("exact_match"),
                "numeric_match": classified.get("numeric_match"),
                "extracted_answer": extraction.answer,
                "hit_max_new_tokens": hit_max_tokens(row),
            }
        per_prompt.append(prompt_record)

    for condition in condition_summaries:
        condition_summaries[condition]["label_counts"] = dict(sorted(label_counts_by_condition[condition].items()))

    compressed_failures = [
        row
        for row in rows
        if row["condition"] in COMPRESSED_CONDITIONS and row["triage_label"] != "PASS_MATCH"
    ]
    representative = compressed_failures[:5]

    compression_loss_likely = sum(1 for row in compressed_failures if row["triage_label"] == "COMPRESSION_LOSS_LIKELY")
    truncation_likely = sum(1 for row in compressed_failures if row["triage_label"] == "TRUNCATION_LIKELY")
    compressed_prompt_available = any(row["compressed_prompt_available"] for row in compressed_failures)

    return {
        "task": "Task 54 compressed GSM8K quality triage",
        "status": "PASS",
        "claim_policy": "preliminary artifact triage only; no new benchmark run and no final correctness claim",
        "inputs": {
            "artifacts": {condition: str(path) for condition, path in ARTIFACTS.items()},
            "dataset": str(DATASET),
        },
        "condition_summaries": condition_summaries,
        "label_counts": dict(sorted(label_counts.items())),
        "label_counts_by_condition": {
            condition: dict(sorted(counter.items())) for condition, counter in sorted(label_counts_by_condition.items())
        },
        "compressed_failure_summary": {
            "compressed_failure_rows": len(compressed_failures),
            "compression_loss_likely_rows": compression_loss_likely,
            "truncation_likely_rows": truncation_likely,
            "compressed_prompt_available": compressed_prompt_available,
            "direct_prompt_removal_audit_possible": compressed_prompt_available,
        },
        "per_prompt": per_prompt,
        "representative_failures": representative,
        "recommendation": {
            "compression_loss_likely": compression_loss_likely > 0,
            "test_max_new_tokens_192_or_256": True,
            "change_prompt_format": True,
            "rationale": (
                "Compressed failures often occur when uncompressed rows succeed, but all rows also hit the 128-token "
                "cap and compressed prompt text is not stored. Add a short final-answer instruction and inspect "
                "compressed prompts/failures before any larger run."
            ),
        },
        "rows": rows,
    }


def write_samples(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in summary["representative_failures"]:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Triage compressed GSM8K Task 53 quality failures")
    parser.add_argument("--output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--samples", default=str(DEFAULT_SAMPLES_OUTPUT))
    args = parser.parse_args()

    summary = analyze()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_samples(summary, Path(args.samples))

    print(f"status={summary['status']}")
    print(f"label_counts={summary['label_counts']}")
    for condition, condition_summary in summary["condition_summaries"].items():
        print(
            f"{condition}: rows={condition_summary['rows']} exact={condition_summary['exact_match_count']} "
            f"numeric={condition_summary['numeric_match_count']} labels={condition_summary['label_counts']}"
        )
    print(f"compressed_failure_summary={summary['compressed_failure_summary']}")


if __name__ == "__main__":
    main()
