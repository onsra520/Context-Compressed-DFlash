from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_system_build_and_evaluation.analysis.t47_quality_refinement import (
    classify_row,
    normalize_text,
)

DEFAULT_PATTERNS = [
    "results/task50_*_n3.jsonl",
    "results/task51_*_n3.jsonl",
    "results/task51_*_n10.jsonl",
]
DEFAULT_JSON_OUTPUT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task52_metric_summary.json")
DEFAULT_CSV_OUTPUT = Path("results/phase_1_system_build_and_evaluation/early_experiments/task52_metric_table.csv")

COMMON_REQUIRED_FIELDS = {
    "condition",
    "prompt_id",
    "input_tokens",
    "output_tokens",
    "generation_time_s",
    "tok_per_sec",
    "acceptance_lengths",
    "tau_mean",
    "vram_allocated_gib",
    "vram_reserved_gib",
    "t_prefill_ms",
    "generated_text",
    "prompt_source",
    "dataset_name",
    "expected_answer",
}
COMPRESSION_FIELDS = {
    "t_compress_ms",
    "R_actual",
    "N_original",
    "N_compressed",
    "keep_rate",
    "compressor_model",
    "question_preserved",
}
DRAFT_CONDITIONS = {"DFlash-R1", "CC-DFlash-R2", "CC-LLM-R2"}
AR_CONDITIONS = {"Baseline-AR", "LLMLingua-AR-R2"}
COMPRESSED_CONDITIONS = {"LLMLingua-AR-R2", "CC-DFlash-R2", "CC-LLM-R2"}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
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


def _values(rows: list[dict[str, Any]], field_name: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(field_name)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def _rate(count: int, denominator: int) -> float:
    return count / denominator if denominator else 0.0


def _path_stage(path: Path) -> str:
    if path.name.startswith("task50_"):
        return "task50_n3"
    if path.name.endswith("_n3.jsonl"):
        return "task51_stage_a_n3"
    if path.name.endswith("_n10.jsonl"):
        return "task51_stage_b_n10"
    return "unknown"


def _generated_repetition_warning(text: str) -> bool:
    words = normalize_text(text).split()
    if len(words) < 24:
        return False
    ngrams = [" ".join(words[index : index + 4]) for index in range(len(words) - 3)]
    if not ngrams:
        return False
    counts = Counter(ngrams)
    most_common = counts.most_common(1)[0][1]
    return most_common >= 4 or (most_common / len(ngrams)) > 0.25


def _schema_issues(rows: list[dict[str, Any]], path: Path) -> list[str]:
    issues: list[str] = []
    for row_index, row in enumerate(rows, start=1):
        missing = sorted(COMMON_REQUIRED_FIELDS - set(row))
        if missing:
            issues.append(f"row {row_index}: missing common fields {missing}")

        condition = str(row.get("condition", ""))
        if condition in COMPRESSED_CONDITIONS:
            missing_compression = sorted(COMPRESSION_FIELDS - set(row))
            if missing_compression:
                issues.append(f"row {row_index}: missing compression fields {missing_compression}")
            if row.get("question_preserved") is not True:
                issues.append(f"row {row_index}: question_preserved must be true for compressed rows")

        if condition in AR_CONDITIONS:
            if row.get("acceptance_lengths") != []:
                issues.append(f"row {row_index}: AR condition must have empty acceptance_lengths")
            if not isinstance(row.get("tau_mean"), (int, float)) or float(row["tau_mean"]) != 0.0:
                issues.append(f"row {row_index}: AR condition must have tau_mean == 0.0")

        if condition in DRAFT_CONDITIONS and row.get("output_tokens", 0) > 0:
            if not isinstance(row.get("acceptance_lengths"), list) or not row.get("acceptance_lengths"):
                issues.append(f"row {row_index}: DFlash condition with output tokens needs acceptance_lengths")

        if not isinstance(row.get("generated_text"), str) or not row.get("generated_text", "").strip():
            issues.append(f"row {row_index}: generated_text missing or empty")

    if not rows:
        issues.append(f"{path}: no rows")
    return issues


def _quality_summary(rows: list[dict[str, Any]], path: Path) -> dict[str, Any]:
    dataset_names = {str(row.get("dataset_name", "")) for row in rows}
    condition = str(rows[0].get("condition", "")) if rows else ""
    generated_present = sum(1 for row in rows if isinstance(row.get("generated_text"), str) and row["generated_text"].strip())
    generated_empty = len(rows) - generated_present
    repetition_warnings = sum(
        1
        for row in rows
        if isinstance(row.get("generated_text"), str) and _generated_repetition_warning(row["generated_text"])
    )

    if dataset_names == {"gsm8k_short"}:
        classified = [
            classify_row(row, row_index=index, condition=condition, artifact=str(path))
            for index, row in enumerate(rows, start=1)
        ]
        numeric_matches = sum(1 for item in classified if item.get("numeric_match"))
        exact_matches = sum(1 for item in classified if item.get("exact_match"))
        wrong_extracted = sum(1 for item in classified if item.get("failure_type") == "extracted_but_wrong")
        ambiguous = sum(1 for item in classified if item.get("failure_type") == "parse_ambiguous")
        missing_final = sum(
            1
            for item in classified
            if item.get("failure_type") in {"no_final_answer_found", "generated_text_missing", "truncated_or_stopped_early"}
        )
        return {
            "quality_policy": "numeric_extraction_exact_match_proxy",
            "generated_text_present": generated_present,
            "generated_text_empty": generated_empty,
            "repetition_warning_count": repetition_warnings,
            "exact_match_count": exact_matches,
            "numeric_match_count": numeric_matches,
            "numeric_match_rate": _rate(numeric_matches, len(rows)),
            "exact_match_rate": _rate(exact_matches, len(rows)),
            "extracted_but_wrong_count": wrong_extracted,
            "ambiguous_count": ambiguous,
            "missing_or_truncated_final_answer_count": missing_final,
        }

    normalized_containment = 0
    exact_containment = 0
    for row in rows:
        expected = row.get("expected_answer")
        generated = row.get("generated_text")
        if not isinstance(expected, str) or not isinstance(generated, str):
            continue
        if expected and expected in generated:
            exact_containment += 1
        if expected and normalize_text(expected) in normalize_text(generated):
            normalized_containment += 1

    return {
        "quality_policy": "normalized_text_containment_proxy",
        "generated_text_present": generated_present,
        "generated_text_empty": generated_empty,
        "repetition_warning_count": repetition_warnings,
        "exact_containment_count": exact_containment,
        "normalized_containment_count": normalized_containment,
        "normalized_containment_rate": _rate(normalized_containment, len(rows)),
        "semantic_correctness_claim": False,
    }


def summarize_artifact(path: Path) -> dict[str, Any]:
    rows = _load_jsonl(path)
    conditions = sorted({str(row.get("condition")) for row in rows})
    datasets = sorted({str(row.get("dataset_name")) for row in rows})
    generation_time = _values(rows, "generation_time_s")
    t_compress = _values(rows, "t_compress_ms")
    e2e_times = [
        float(row.get("generation_time_s", 0) or 0) + float(row.get("t_compress_ms", 0) or 0) / 1000.0
        for row in rows
    ]

    schema_issues = _schema_issues(rows, path)
    output_tokens = _values(rows, "output_tokens")
    output_token_sum = sum(output_tokens)
    e2e_sum = sum(e2e_times)
    e2e_tok_per_sec = output_token_sum / e2e_sum if e2e_sum > 0 else 0.0

    return {
        "path": str(path),
        "stage": _path_stage(path),
        "status": "PASS" if not schema_issues else "FAIL",
        "schema_issues": schema_issues,
        "rows": len(rows),
        "condition": conditions[0] if len(conditions) == 1 else "mixed",
        "dataset_name": datasets[0] if len(datasets) == 1 else "mixed",
        "avg_input_tokens": _mean(_values(rows, "input_tokens")),
        "avg_output_tokens": _mean(output_tokens),
        "avg_generation_time_s": _mean(generation_time),
        "median_generation_time_s": _median(generation_time),
        "avg_tok_per_sec_generation_only": _mean(_values(rows, "tok_per_sec")),
        "median_tok_per_sec_generation_only": _median(_values(rows, "tok_per_sec")),
        "avg_e2e_time_s": _mean(e2e_times),
        "e2e_output_tok_per_sec": e2e_tok_per_sec,
        "avg_t_compress_ms": _mean(t_compress),
        "avg_t_prefill_ms": _mean(_values(rows, "t_prefill_ms")),
        "avg_R_actual": _mean(_values(rows, "R_actual")),
        "avg_N_original": _mean(_values(rows, "N_original")),
        "avg_N_compressed": _mean(_values(rows, "N_compressed")),
        "avg_input_reduction_tokens": _mean(
            [
                float(row.get("N_original", 0) or 0) - float(row.get("N_compressed", 0) or 0)
                for row in rows
                if isinstance(row.get("N_original"), (int, float)) and isinstance(row.get("N_compressed"), (int, float))
            ]
        ),
        "avg_tau_mean": _mean(_values(rows, "tau_mean")),
        "max_vram_allocated_gib": max(_values(rows, "vram_allocated_gib") or [0.0]),
        "max_vram_reserved_gib": max(_values(rows, "vram_reserved_gib") or [0.0]),
        "generated_text_all_present": all(isinstance(row.get("generated_text"), str) and row["generated_text"].strip() for row in rows),
        "quality": _quality_summary(rows, path),
    }


def _collect_paths(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(Path().glob(pattern))
    return sorted(dict.fromkeys(paths))


def _comparisons(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for item in artifacts:
        grouped[(item["stage"], item["dataset_name"], item["condition"])] = item

    comparisons: dict[str, Any] = {}
    for stage in sorted({item["stage"] for item in artifacts}):
        for dataset in sorted({item["dataset_name"] for item in artifacts if item["stage"] == stage}):
            dflash = grouped.get((stage, dataset, "DFlash-R1"))
            cc = grouped.get((stage, dataset, "CC-DFlash-R2")) or grouped.get((stage, dataset, "CC-LLM-R2"))
            baseline = grouped.get((stage, dataset, "Baseline-AR"))
            llm_ar = grouped.get((stage, dataset, "LLMLingua-AR-R2"))
            label = f"{stage}:{dataset}"
            entry: dict[str, Any] = {}
            if dflash and cc:
                entry["cc_vs_dflash_generation_tok_s_ratio"] = (
                    cc["avg_tok_per_sec_generation_only"] / dflash["avg_tok_per_sec_generation_only"]
                    if dflash["avg_tok_per_sec_generation_only"]
                    else 0.0
                )
                entry["cc_vs_dflash_e2e_time_ratio"] = (
                    cc["avg_e2e_time_s"] / dflash["avg_e2e_time_s"] if dflash["avg_e2e_time_s"] else 0.0
                )
                entry["cc_beats_dflash_generation_only"] = (
                    cc["avg_tok_per_sec_generation_only"] > dflash["avg_tok_per_sec_generation_only"]
                )
                entry["cc_beats_dflash_e2e"] = cc["avg_e2e_time_s"] < dflash["avg_e2e_time_s"]
            if baseline and dflash:
                entry["dflash_vs_baseline_generation_tok_s_ratio"] = (
                    dflash["avg_tok_per_sec_generation_only"] / baseline["avg_tok_per_sec_generation_only"]
                    if baseline["avg_tok_per_sec_generation_only"]
                    else 0.0
                )
            if baseline and llm_ar:
                entry["llmlingua_ar_vs_baseline_e2e_time_ratio"] = (
                    llm_ar["avg_e2e_time_s"] / baseline["avg_e2e_time_s"]
                    if baseline["avg_e2e_time_s"]
                    else 0.0
                )
            if entry:
                comparisons[label] = entry
    return comparisons


def analyze(patterns: list[str]) -> dict[str, Any]:
    paths = _collect_paths(patterns)
    artifacts = [summarize_artifact(path) for path in paths]
    status = "PASS" if all(item["status"] == "PASS" for item in artifacts) else "FAIL"
    return {
        "task": "Task 52 artifact audit and metric summary",
        "claim_policy": "preliminary smoke-level only; no final speedup or correctness claim",
        "status": status,
        "input_patterns": patterns,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "comparisons": _comparisons(artifacts),
        "next_run_recommendation": (
            "Audit quality/anomalies before any larger run. If proceeding, use max_new_tokens>=128 for quality-oriented "
            "GSM8K runs and keep QMSum interpretation as long-answer proxy unless manual/semantic judging is added."
        ),
    }


def _write_csv(summary: dict[str, Any], path: Path) -> None:
    fields = [
        "stage",
        "dataset_name",
        "condition",
        "rows",
        "status",
        "avg_input_tokens",
        "avg_output_tokens",
        "avg_generation_time_s",
        "avg_tok_per_sec_generation_only",
        "avg_e2e_time_s",
        "e2e_output_tok_per_sec",
        "avg_t_compress_ms",
        "avg_t_prefill_ms",
        "avg_R_actual",
        "avg_tau_mean",
        "max_vram_allocated_gib",
        "max_vram_reserved_gib",
        "generated_text_all_present",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for artifact in summary["artifacts"]:
            writer.writerow({field: artifact.get(field) for field in fields})


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Task 50/51 benchmark smoke artifacts")
    parser.add_argument("patterns", nargs="*", default=DEFAULT_PATTERNS)
    parser.add_argument("--output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_OUTPUT))
    args = parser.parse_args()

    summary = analyze(args.patterns)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_csv(summary, Path(args.csv))

    print(f"status={summary['status']} artifacts={summary['artifact_count']}")
    for artifact in summary["artifacts"]:
        print(
            f"{artifact['status']} {artifact['stage']} {artifact['dataset_name']} {artifact['condition']} "
            f"rows={artifact['rows']} avg_tok_s={artifact['avg_tok_per_sec_generation_only']:.2f} "
            f"e2e_tok_s={artifact['e2e_output_tok_per_sec']:.2f} "
            f"avg_t_compress_ms={artifact['avg_t_compress_ms']:.2f} "
            f"quality={artifact['quality']['quality_policy']}"
        )
    if summary["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
