from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_2_system_optimization.analysis import task95b_quality_proxy_calibration as t95b


DEFAULT_RUN_ARTIFACT = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task100b_light_gpu_n100_controlled_run/runs/"
    "20260621_1555_cc_dflash_r2_light_gpu_seed42_n100_mnt256.jsonl"
)
DEFAULT_TASK100B_SUMMARY = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task100b_light_gpu_n100_controlled_run/summary/"
    "task100b_light_gpu_n100_summary.json"
)
DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task100c_optimization_gap_analysis"
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: line {line_number} is not a JSON object")
        rows.append(payload)
    return rows


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        rows = [{"section": "", "metric": "", "value": "", "note": ""}]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _numeric(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _e2e_time(row: dict[str, Any]) -> float | None:
    direct = _numeric(row, "e2e_time_s")
    if direct is not None:
        return direct
    generation = _numeric(row, "generation_time_s")
    compress_ms = _numeric(row, "t_compress_ms")
    if generation is None:
        return None
    return generation + ((compress_ms or 0.0) / 1000.0)


def _rate(count: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(count / total, 6)


def _values(records: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for record in records:
        value = record.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 6)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return round(ordered[lower] + ((ordered[upper] - ordered[lower]) * fraction), 6)


def _stats(records: list[dict[str, Any]], key: str) -> dict[str, float | None]:
    values = _values(records, key)
    if not values:
        return {"avg": None, "min": None, "max": None, "p95": None}
    return {
        "avg": round(mean(values), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "p95": _percentile(values, 0.95),
    }


def _preview(text: Any, *, limit: int = 260) -> str:
    if not isinstance(text, str):
        return ""
    compact = " ".join(text.split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def _tail(text: Any, *, limit: int = 260) -> str:
    if not isinstance(text, str):
        return ""
    compact = " ".join(text.split())
    return ("..." if len(compact) > limit else "") + compact[-limit:]


def _failure_flags(rows: list[dict[str, Any]]) -> dict[str, Any]:
    messages: list[str] = []
    for row in rows:
        for key, value in row.items():
            lowered = str(key).lower()
            if ("failure" in lowered or "oom" in lowered or "cuda" in lowered) and value not in (None, "", False):
                if lowered in {"compressor_device_map", "requested_compressor_device_map", "device"}:
                    continue
                messages.append(str(value))
    haystack = " ".join(messages).lower()
    return {
        "failure_messages": messages,
        "oom_or_cuda_failure": "oom" in haystack or "cuda" in haystack,
    }


def build_row_records(rows: list[dict[str, Any]], *, artifact: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        label = t95b.calibrate_row(row, profile="light_gpu_n100", row_index=index, artifact=artifact)
        category = str(label.get("calibrated_label") or "proxy_uncertain")
        e2e_time_s = _e2e_time(row)
        record = {
            "row_index": index,
            "fixture_id": row.get("fixture_id") or row.get("dataset_id") or index,
            "dataset_id": row.get("dataset_id"),
            "prompt_id": row.get("prompt_id", row.get("benchmark_prompt_index")),
            "expected_answer": label.get("expected_answer"),
            "extracted_answer": label.get("strict_extracted_answer"),
            "category": category,
            "strict_correct": bool(label.get("strict_correct")),
            "final_answer_marker_present": bool(label.get("final_answer_marker_present")),
            "exact_containment": bool(label.get("exact_containment")),
            "generated_text_preview": _preview(row.get("generated_text")),
            "generated_text_tail": _tail(row.get("generated_text")),
            "output_tokens": row.get("output_tokens", row.get("generated_token_count")),
            "max_new_tokens": row.get("max_new_tokens"),
            "t_compress_ms": _numeric(row, "t_compress_ms"),
            "e2e_time_s": e2e_time_s,
            "tokens_per_second": _numeric(row, "tokens_per_second", "tok_per_sec"),
            "tau_mean": _numeric(row, "tau_mean"),
            "t_prefill_ms": _numeric(row, "t_prefill_ms"),
            "R_actual": _numeric(row, "R_actual", "actual_compression_ratio", "compression_ratio"),
            "vram_allocated_gib": _numeric(row, "vram_allocated_gib"),
            "vram_reserved_gib": _numeric(row, "vram_reserved_gib"),
            "prefill_vram_allocated_gib": _numeric(row, "prefill_vram_allocated_gib"),
            "prefill_vram_reserved_gib": _numeric(row, "prefill_vram_reserved_gib"),
            "notes": label.get("notes", []),
        }
        records.append(record)
    return records


def failure_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if record.get("category") != "strict_correct" or not record.get("strict_correct")
    ]


def slowest_rows(records: list[dict[str, Any]], *, limit: int = 10) -> list[dict[str, Any]]:
    return sorted(
        records,
        key=lambda record: record.get("e2e_time_s") if isinstance(record.get("e2e_time_s"), (int, float)) else -1.0,
        reverse=True,
    )[:limit]


def _highest_rows(records: list[dict[str, Any]], key: str, *, limit: int = 10) -> list[dict[str, Any]]:
    return sorted(
        records,
        key=lambda record: record.get(key) if isinstance(record.get(key), (int, float)) else -1.0,
        reverse=True,
    )[:limit]


def _lowest_rows(records: list[dict[str, Any]], key: str, *, limit: int = 10) -> list[dict[str, Any]]:
    valued = [record for record in records if isinstance(record.get(key), (int, float))]
    return sorted(valued, key=lambda record: record[key])[:limit]


def runtime_bottlenecks(records: list[dict[str, Any]]) -> dict[str, Any]:
    failures = failure_rows(records)
    slow_top = slowest_rows(records, limit=max(1, min(10, len(records))))
    slow_ids = {record.get("fixture_id") for record in slow_top}
    failure_ids = {record.get("fixture_id") for record in failures}
    return {
        "t_compress_ms": _stats(records, "t_compress_ms"),
        "e2e_time_s": _stats(records, "e2e_time_s"),
        "tokens_per_second": _stats(records, "tokens_per_second"),
        "tau_mean": _stats(records, "tau_mean"),
        "t_prefill_ms": _stats(records, "t_prefill_ms"),
        "vram_allocated_gib": _stats(records, "vram_allocated_gib"),
        "vram_reserved_gib": _stats(records, "vram_reserved_gib"),
        "highest_t_compress_rows": _highest_rows(records, "t_compress_ms", limit=10),
        "lowest_tokens_per_second_rows": _lowest_rows(records, "tokens_per_second", limit=10),
        "abnormal_tau_rows": _highest_rows(records, "tau_mean", limit=5)
        + _lowest_rows(records, "tau_mean", limit=5),
        "failure_latency_correlation": {
            "failure_row_count": len(failures),
            "slowest_row_count": len(slow_top),
            "failure_rows_in_slowest_top": len(slow_ids & failure_ids),
            "failure_avg_e2e_time_s": _stats(failures, "e2e_time_s")["avg"],
            "strict_correct_avg_e2e_time_s": _stats(
                [record for record in records if record.get("strict_correct")], "e2e_time_s"
            )["avg"],
        },
    }


def compression_behavior(records: list[dict[str, Any]]) -> dict[str, Any]:
    failures = failure_rows(records)
    r_stats = _stats(records, "R_actual")
    return {
        "R_actual": r_stats,
        "stable_around_2": (
            r_stats["min"] is not None
            and r_stats["max"] is not None
            and abs(float(r_stats["min"]) - 2.0) <= 0.25
            and abs(float(r_stats["max"]) - 2.0) <= 0.25
        ),
        "failure_rows_R_actual": _stats(failures, "R_actual"),
        "compression_overhead_consistently_low": (
            _stats(records, "t_compress_ms")["p95"] is not None
            and float(_stats(records, "t_compress_ms")["p95"]) < 50.0
        ),
    }


def gpu_vram_stability(records: list[dict[str, Any]], rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    flags = _failure_flags(rows or [])
    return {
        "vram_allocated_gib": _stats(records, "vram_allocated_gib"),
        "vram_reserved_gib": _stats(records, "vram_reserved_gib"),
        "prefill_vram_allocated_gib": _stats(records, "prefill_vram_allocated_gib"),
        "prefill_vram_reserved_gib": _stats(records, "prefill_vram_reserved_gib"),
        "oom_or_cuda_failure": flags["oom_or_cuda_failure"],
        "failure_messages": flags["failure_messages"],
        "bounded_in_this_run": not flags["oom_or_cuda_failure"] and _stats(records, "vram_reserved_gib")["max"] is not None,
        "deployment_readiness_claimed": False,
    }


def quality_gaps(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    counts = {
        "strict_correct": sum(1 for record in records if record.get("strict_correct")),
        "cap_limited_incomplete": sum(1 for record in records if record.get("category") == "cap_limited_incomplete"),
        "strict_wrong_numeric": sum(1 for record in records if record.get("category") == "strict_wrong_numeric"),
        "answer_missing": sum(1 for record in records if record.get("category") == "answer_missing"),
        "proxy_uncertain": sum(1 for record in records if record.get("category") == "proxy_uncertain"),
        "format_or_extraction_sensitive": sum(
            1 for record in records if record.get("category") == "format_or_extraction_sensitive"
        ),
        "final_answer_marker": sum(1 for record in records if record.get("final_answer_marker_present")),
        "exact_containment": sum(1 for record in records if record.get("exact_containment")),
    }
    return {
        "row_count": total,
        "strict_correct_count": counts["strict_correct"],
        "strict_correct_rate": _rate(counts["strict_correct"], total),
        "cap_limited_incomplete_count": counts["cap_limited_incomplete"],
        "cap_limited_incomplete_rate": _rate(counts["cap_limited_incomplete"], total),
        "strict_wrong_numeric_count": counts["strict_wrong_numeric"],
        "strict_wrong_numeric_rate": _rate(counts["strict_wrong_numeric"], total),
        "answer_missing_count": counts["answer_missing"],
        "answer_missing_rate": _rate(counts["answer_missing"], total),
        "proxy_uncertain_count": counts["proxy_uncertain"],
        "proxy_uncertain_rate": _rate(counts["proxy_uncertain"], total),
        "format_or_extraction_sensitive_count": counts["format_or_extraction_sensitive"],
        "format_or_extraction_sensitive_rate": _rate(counts["format_or_extraction_sensitive"], total),
        "final_answer_marker_count": counts["final_answer_marker"],
        "final_answer_marker_rate": _rate(counts["final_answer_marker"], total),
        "exact_containment_diagnostic_count": counts["exact_containment"],
        "exact_containment_diagnostic_rate": _rate(counts["exact_containment"], total),
        "non_strict_row_count": total - counts["strict_correct"],
        "non_strict_row_categories": {
            key: counts[key]
            for key in (
                "cap_limited_incomplete",
                "strict_wrong_numeric",
                "answer_missing",
                "proxy_uncertain",
                "format_or_extraction_sensitive",
            )
        },
    }


def build_gap_summary(records: list[dict[str, Any]], *, task100b_summary: dict[str, Any], rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "task": "Task100C",
        "decision": "PASS",
        "source_task": "Task100B",
        "source_summary_decision": task100b_summary.get("decision"),
        "quality_gaps": quality_gaps(records),
        "runtime_bottlenecks": runtime_bottlenecks(records),
        "compression_behavior": compression_behavior(records),
        "gpu_vram_stability": gpu_vram_stability(records, rows),
        "reference_interpretation": {
            "task99r_light_gpu_n10": "bounded scale-up reference only; sample size differs",
            "task96_light_cpu_n30": "bounded CPU reference only; sample size differs",
            "task96_large_cpu_n30": "bounded CPU historical/control reference only; sample size differs",
            "dflash_r1_task88": "historical-only reference if mentioned; settings differ",
        },
        "analysis_scope": {
            "model_loading": False,
            "gpu_run": False,
            "benchmark_run": False,
            "n100_rerun": False,
            "qmsum_run": False,
            "full_matrix": False,
            "keep_rate_tuning": False,
            "llm_judge": False,
        },
    }


def claim_risk_register(gap_summary: dict[str, Any]) -> dict[str, Any]:
    quality = gap_summary["quality_gaps"]
    return {
        "task": "Task100C",
        "risks": [
            {
                "risk_id": "final_speedup_not_proven",
                "severity": "high",
                "reason": "Task100B is one Light GPU condition, not a full matrix or Baseline/DFlash-normalized final benchmark.",
                "blocked_claim": "final speedup is proven",
            },
            {
                "risk_id": "final_quality_not_proven",
                "severity": "high",
                "reason": "Task100B uses deterministic GSM8K numeric proxy only.",
                "blocked_claim": "final quality is proven",
            },
            {
                "risk_id": "qmsum_semantic_correctness_not_tested",
                "severity": "high",
                "reason": "Task100B did not run QMSum and QMSum remains diagnostic-only in project policy.",
                "blocked_claim": "QMSum semantic correctness is proven",
            },
            {
                "risk_id": "deployment_8gb_readiness_not_proven",
                "severity": "high",
                "reason": "Observed VRAM is useful runtime evidence but not deployment validation.",
                "blocked_claim": "deployment or 8GB readiness is proven",
            },
            {
                "risk_id": "full_benchmark_not_run",
                "severity": "high",
                "reason": "No full matrix was run in Task100B or Task100C.",
                "blocked_claim": "full benchmark completed",
            },
            {
                "risk_id": "dflash_r1_not_proven_broken",
                "severity": "medium",
                "reason": "DFlash-R1 is only a historical reference here and was not rerun in Task100B.",
                "blocked_claim": "DFlash-R1 is broken",
            },
            {
                "risk_id": "gpu_default_switch_not_justified",
                "severity": "medium",
                "reason": "Task100B supports bounded Light GPU candidacy, not a default config change.",
                "blocked_claim": "Light GPU should be default",
            },
            {
                "risk_id": "remaining_cap_limited_rows",
                "severity": "medium",
                "reason": f"Task100B still has {quality['cap_limited_incomplete_count']}/{quality['row_count']} cap-limited incomplete rows.",
                "blocked_claim": "quality failures are solved",
            },
            {
                "risk_id": "remaining_strict_wrong_numeric_rows",
                "severity": "medium",
                "reason": f"Task100B still has {quality['strict_wrong_numeric_count']}/{quality['row_count']} strict wrong numeric rows.",
                "blocked_claim": "numeric correctness is solved",
            },
            {
                "risk_id": "task96_references_not_n100",
                "severity": "medium",
                "reason": "Task96 light/large CPU references are n30, not equal-setting n100 comparisons.",
                "blocked_claim": "Task100B proves equal-setting superiority over Task96 references",
            },
        ],
    }


def build_recommendation(gap_summary: dict[str, Any], risk_register: dict[str, Any]) -> dict[str, Any]:
    quality = gap_summary["quality_gaps"]
    vram = gap_summary["gpu_vram_stability"]
    serious_bug = False
    if quality["row_count"] <= 0 or vram["oom_or_cuda_failure"]:
        serious_bug = True
    next_step = "T101_Final_Claim_Boundary_Audit" if not serious_bug else "Optional_targeted_fix_or_audit_before_T101"
    return {
        "decision": "PASS" if not serious_bug else "PARTIAL",
        "next_step": next_step,
        "reason": (
            "Task100B artifacts are complete enough for claim-risk audit; remaining issues are bounded claim risks, not required rerun triggers."
            if not serious_bug
            else "Artifact completeness or stability issue needs targeted audit before final claim boundary."
        ),
        "recommend_another_benchmark_by_default": False,
        "recommend_qmsum_by_default": False,
        "recommend_full_matrix_by_default": False,
        "recommend_default_gpu_switch": False,
        "risk_count": len(risk_register["risks"]),
    }


def _bottleneck_table(gap_summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section, metrics in (
        ("runtime", gap_summary["runtime_bottlenecks"]),
        ("compression", gap_summary["compression_behavior"]),
        ("gpu_vram", gap_summary["gpu_vram_stability"]),
    ):
        for metric, value in metrics.items():
            if isinstance(value, dict) and {"avg", "min", "max", "p95"} <= set(value):
                rows.append(
                    {
                        "section": section,
                        "metric": metric,
                        "avg": value["avg"],
                        "min": value["min"],
                        "max": value["max"],
                        "p95": value["p95"],
                        "note": "",
                    }
                )
    return rows


def analyze(
    *,
    run_artifact: Path = DEFAULT_RUN_ARTIFACT,
    task100b_summary: Path = DEFAULT_TASK100B_SUMMARY,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(run_artifact)
    summary_payload = load_json(task100b_summary) if task100b_summary.exists() else {}
    records = build_row_records(rows, artifact=run_artifact)
    gap_summary = build_gap_summary(records, task100b_summary=summary_payload, rows=rows)
    risks = claim_risk_register(gap_summary)
    recommendation = build_recommendation(gap_summary, risks)
    gap_summary["recommendation"] = recommendation

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "task100c_gap_summary.json", gap_summary)
    _write_jsonl(output_dir / "task100c_failure_rows.jsonl", failure_rows(records))
    _write_jsonl(output_dir / "task100c_slowest_rows.jsonl", slowest_rows(records, limit=10))
    _write_csv(output_dir / "task100c_bottleneck_table.csv", _bottleneck_table(gap_summary))
    _write_json(output_dir / "task100c_recommendation.json", recommendation)
    _write_json(output_dir / "task100c_claim_risk_register.json", risks)
    return gap_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze Task100C optimization gaps from Task100B artifacts.")
    parser.add_argument("--run-artifact", type=Path, default=DEFAULT_RUN_ARTIFACT)
    parser.add_argument("--task100b-summary", type=Path, default=DEFAULT_TASK100B_SUMMARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    analyze(
        run_artifact=args.run_artifact,
        task100b_summary=args.task100b_summary,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
