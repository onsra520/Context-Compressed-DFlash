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


DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task100b_light_gpu_n100_controlled_run"
)
DEFAULT_RUN_GLOB = "*_cc_dflash_r2_light_gpu_seed42_n100_mnt256.jsonl"
DEFAULT_TASK99R_SUMMARY = Path(
    "results/phase_2_system_optimization/compressor_comparison/"
    "task99_light_compressor_gpu_placement_feasibility/resume_gpu/summary/"
    "task99r_gpu_placement_summary.json"
)
DEFAULT_TASK96_LIGHT = Path(
    "results/phase_2_system_optimization/compressor_comparison/"
    "task99_light_compressor_gpu_placement_feasibility/static_audit/"
    "task99_task96_light_cpu_reference.json"
)
DEFAULT_TASK96_LARGE = Path(
    "results/phase_2_system_optimization/compressor_comparison/"
    "task99_light_compressor_gpu_placement_feasibility/static_audit/"
    "task99_task96_large_cpu_reference.json"
)
DEFAULT_DFLASH = Path(
    "results/phase_2_system_optimization/compressor_comparison/"
    "task99_light_compressor_gpu_placement_feasibility/static_audit/"
    "task99_task88_dflash_r1_historical_reference.json"
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
        rows = [{"section": "", "label": "", "value": "", "note": ""}]
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


def _numbers(values: list[float | None]) -> list[float]:
    return [float(value) for value in values if isinstance(value, (int, float))]


def _avg(values: list[float | None]) -> float | None:
    nums = _numbers(values)
    if not nums:
        return None
    return round(mean(nums), 6)


def _min(values: list[float | None]) -> float | None:
    nums = _numbers(values)
    return round(min(nums), 6) if nums else None


def _max(values: list[float | None]) -> float | None:
    nums = _numbers(values)
    return round(max(nums), 6) if nums else None


def _rate(count: Any, total: Any) -> float | None:
    if isinstance(count, bool) or isinstance(total, bool):
        return None
    if not isinstance(count, (int, float)) or not isinstance(total, (int, float)):
        return None
    if total <= 0:
        return None
    return round(float(count) / float(total), 6)


def _round2(value: Any) -> Any:
    return round(value, 2) if isinstance(value, float) else value


def _e2e_time(row: dict[str, Any]) -> float | None:
    direct = _numeric(row, "e2e_time_s")
    if direct is not None:
        return direct
    generation = _numeric(row, "generation_time_s")
    compress_ms = _numeric(row, "t_compress_ms")
    if generation is None:
        return None
    return generation + ((compress_ms or 0.0) / 1000.0)


def _failure_flags(rows: list[dict[str, Any]]) -> dict[str, Any]:
    messages: list[str] = []
    types: list[str] = []
    for row in rows:
        for key, value in row.items():
            lowered = str(key).lower()
            if "failure" not in lowered and "oom" not in lowered:
                continue
            if value in (None, "", False):
                continue
            text = str(value).strip()
            messages.append(text)
            if "type" in lowered:
                types.append(text.lower())
    haystack = [item.lower() for item in messages + types]
    oom_or_cuda = any("oom" in item or "cuda" in item for item in haystack)
    return {
        "failure_messages": messages,
        "failure_types": types,
        "oom_or_cuda_failure": oom_or_cuda,
    }


def _metadata_values(rows: list[dict[str, Any]], key: str) -> list[str]:
    return sorted({str(row.get(key)) for row in rows})


def _metric_summary(rows: list[dict[str, Any]], metric_name: str, *keys: str) -> dict[str, float | None]:
    values = [_numeric(row, *keys) for row in rows]
    return {
        f"avg_{metric_name}": _avg(values),
        f"min_{metric_name}": _min(values),
        f"max_{metric_name}": _max(values),
    }


def summarize_light_gpu_run(path: Path) -> dict[str, Any]:
    return summarize_light_gpu_run_from_rows(load_jsonl(path), artifact=path)


def summarize_light_gpu_run_from_rows(rows: list[dict[str, Any]], *, artifact: Path) -> dict[str, Any]:
    flags = _failure_flags(rows)
    labels = [
        t95b.calibrate_row(row, profile="light_gpu_n100", row_index=index, artifact=artifact)
        for index, row in enumerate(rows, start=1)
    ]
    label_counts = {
        label: sum(1 for item in labels if item.get("calibrated_label") == label)
        for label in (
            "strict_correct",
            "strict_wrong_numeric",
            "cap_limited_incomplete",
            "format_or_extraction_sensitive",
            "answer_missing",
            "proxy_uncertain",
        )
    }
    metadata_ok = bool(rows) and all(
        row.get("condition") == "CC-DFlash-R2"
        and row.get("dataset_name") == "gsm8k_short"
        and str(row.get("compressor_profile")) == "light"
        and str(row.get("compressor_device_map")) in {"cuda", "cuda:0"}
        and str(row.get("requested_compressor_device_map")) in {"cuda", "cuda:0"}
        and row.get("local_files_only") is True
        and bool(row.get("compressor_path"))
        and bool(row.get("resolved_compressor_path"))
        for row in rows
    )
    e2e_values = [_e2e_time(row) for row in rows]
    generated_text_missing = sum(
        1 for row in rows if not isinstance(row.get("generated_text"), str) or not row.get("generated_text", "").strip()
    )
    summary: dict[str, Any] = {
        "artifact": str(artifact),
        "row_count": len(rows),
        "expected_row_count": 100,
        "is_complete_n100": len(rows) == 100,
        "metadata_ok": metadata_ok,
        "conditions": _metadata_values(rows, "condition"),
        "datasets": _metadata_values(rows, "dataset_name"),
        "compressor_profiles": _metadata_values(rows, "compressor_profile"),
        "compressor_device_maps": _metadata_values(rows, "compressor_device_map"),
        "requested_compressor_device_maps": _metadata_values(rows, "requested_compressor_device_map"),
        "local_files_only_values": _metadata_values(rows, "local_files_only"),
        "compressor_profile": rows[0].get("compressor_profile") if rows else None,
        "compressor_device_map": rows[0].get("compressor_device_map") if rows else None,
        "requested_compressor_device_map": rows[0].get("requested_compressor_device_map") if rows else None,
        "compressor_path": rows[0].get("compressor_path") if rows else None,
        "resolved_compressor_path": rows[0].get("resolved_compressor_path") if rows else None,
        "local_files_only": rows[0].get("local_files_only") if rows else None,
        "failure_flags": flags,
        "strict_correct_count": sum(1 for item in labels if item.get("strict_correct")),
        "cap_limited_incomplete_count": label_counts["cap_limited_incomplete"],
        "final_answer_marker_count": sum(1 for item in labels if item.get("final_answer_marker_present")),
        "strict_wrong_numeric_count": label_counts["strict_wrong_numeric"],
        "answer_missing_count": label_counts["answer_missing"],
        "proxy_uncertain_count": label_counts["proxy_uncertain"],
        "exact_containment_diagnostic_count": sum(1 for item in labels if item.get("exact_containment")),
        "invalid_or_malformed_generated_text_count": generated_text_missing,
        "calibrated_label_counts": label_counts,
        "labels": labels,
        "strict_correct_rate": _rate(sum(1 for item in labels if item.get("strict_correct")), len(rows)),
        "cap_limited_incomplete_rate": _rate(label_counts["cap_limited_incomplete"], len(rows)),
    }
    summary.update(_metric_summary(rows, "t_compress_ms", "t_compress_ms"))
    summary.update(_metric_summary(rows, "R_actual", "R_actual", "actual_compression_ratio", "compression_ratio"))
    summary.update(
        {
            "avg_e2e_time_s": _avg(e2e_values),
            "min_e2e_time_s": _min(e2e_values),
            "max_e2e_time_s": _max(e2e_values),
        }
    )
    summary.update(_metric_summary(rows, "tokens_per_second", "tokens_per_second", "tok_per_sec"))
    summary.update(_metric_summary(rows, "tau_mean", "tau_mean"))
    summary.update(_metric_summary(rows, "t_prefill_ms", "t_prefill_ms"))
    summary.update(_metric_summary(rows, "vram_allocated_gib", "vram_allocated_gib"))
    summary.update(_metric_summary(rows, "vram_reserved_gib", "vram_reserved_gib"))
    summary.update(_metric_summary(rows, "prefill_vram_allocated_gib", "prefill_vram_allocated_gib"))
    summary.update(_metric_summary(rows, "prefill_vram_reserved_gib", "prefill_vram_reserved_gib"))
    return summary


def load_reference(path: Path, *, role: str, historical_only: bool = False) -> dict[str, Any]:
    payload = load_json(path)
    if "gpu_run" in payload and isinstance(payload["gpu_run"], dict):
        reference = dict(payload["gpu_run"])
        reference["source_task"] = payload.get("task", "Task99-R")
        reference["comparison_role"] = role
    else:
        reference = dict(payload)
    reference["path"] = str(path)
    reference["historical_only"] = bool(historical_only or reference.get("historical_only"))
    reference["comparison_role"] = role
    return reference


def _comparison(run_summary: dict[str, Any], reference: dict[str, Any], *, label: str) -> dict[str, Any]:
    ref_row_count = reference.get("row_count", reference.get("n"))
    ref_mnt = reference.get("max_new_tokens")
    settings_match = (
        reference.get("condition") == "CC-DFlash-R2"
        and ref_row_count == run_summary.get("row_count")
        and ref_mnt == 256
        and not reference.get("historical_only")
    )
    historical_only = bool(reference.get("historical_only"))
    comparison_class = "historical_reference" if historical_only else ("equal_setting" if settings_match else "bounded_reference")
    return {
        "label": label,
        "comparison_class": comparison_class,
        "historical_only": historical_only,
        "settings_match": settings_match,
        "reference": reference,
        "comparisons": {
            "strict_correct_rate_delta": (
                round(
                    (run_summary.get("strict_correct_rate") or 0.0)
                    - (_rate(reference.get("strict_correct_count"), ref_row_count) or 0.0),
                    6,
                )
                if _rate(reference.get("strict_correct_count"), ref_row_count) is not None
                else None
            ),
            "cap_limited_incomplete_rate_delta": (
                round(
                    (run_summary.get("cap_limited_incomplete_rate") or 0.0)
                    - (_rate(reference.get("cap_limited_incomplete_count"), ref_row_count) or 0.0),
                    6,
                )
                if _rate(reference.get("cap_limited_incomplete_count"), ref_row_count) is not None
                else None
            ),
            "avg_t_compress_ms_delta": _delta(run_summary, reference, "avg_t_compress_ms"),
            "avg_e2e_time_s_delta": _delta(run_summary, reference, "avg_e2e_time_s"),
            "avg_tokens_per_second_delta": _delta(run_summary, reference, "avg_tokens_per_second"),
            "avg_tau_mean_delta": _delta(run_summary, reference, "avg_tau_mean"),
            "avg_t_prefill_ms_delta": _delta(run_summary, reference, "avg_t_prefill_ms"),
            "avg_R_actual_delta": _delta(run_summary, reference, "avg_R_actual"),
        },
        "caveat": (
            "Historical-only reference; settings differ and this is not an apples-to-apples claim."
            if historical_only
            else "Bounded reference comparison because sample size or setup differs."
            if not settings_match
            else "Equal-setting comparison."
        ),
    }


def _delta(run_summary: dict[str, Any], reference: dict[str, Any], key: str) -> float | None:
    left = run_summary.get(key)
    right = reference.get(key)
    if isinstance(left, (int, float)) and not isinstance(left, bool) and isinstance(right, (int, float)):
        return round(float(left) - float(right), 6)
    return None


def build_reference_comparisons(
    *,
    run_summary: dict[str, Any],
    task99r_reference: dict[str, Any],
    task96_light_reference: dict[str, Any],
    task96_large_reference: dict[str, Any],
    dflash_reference: dict[str, Any] | None,
) -> dict[str, Any]:
    comparisons = {
        "light_gpu_n100_vs_task99r_light_gpu_n10": _comparison(
            run_summary,
            task99r_reference,
            label="Task99-R light GPU n10",
        ),
        "light_gpu_n100_vs_task96_light_cpu_n30": _comparison(
            run_summary,
            task96_light_reference,
            label="Task96 light CPU n30",
        ),
        "light_gpu_n100_vs_task96_large_cpu_n30": _comparison(
            run_summary,
            task96_large_reference,
            label="Task96 large CPU n30",
        ),
    }
    if dflash_reference is not None:
        comparisons["light_gpu_n100_vs_dflash_r1_historical"] = _comparison(
            run_summary,
            dflash_reference,
            label="Task88 DFlash-R1 historical",
        )
    return comparisons


def build_recommendation(
    *,
    run_summary: dict[str, Any],
    task99r_reference: dict[str, Any],
    task96_light_reference: dict[str, Any],
) -> dict[str, Any]:
    failure = run_summary["failure_flags"]["oom_or_cuda_failure"]
    metadata_ok = bool(run_summary.get("metadata_ok"))
    complete = run_summary.get("row_count") == 100
    strict_rate = run_summary.get("strict_correct_rate")
    cap_rate = run_summary.get("cap_limited_incomplete_rate")
    task96_strict_rate = _rate(
        task96_light_reference.get("strict_correct_count"),
        task96_light_reference.get("row_count", task96_light_reference.get("n")),
    )
    task96_cap_rate = _rate(
        task96_light_reference.get("cap_limited_incomplete_count"),
        task96_light_reference.get("row_count", task96_light_reference.get("n")),
    )
    t_compress_delta = _delta(run_summary, task96_light_reference, "avg_t_compress_ms")
    e2e_delta = _delta(run_summary, task96_light_reference, "avg_e2e_time_s")

    if failure and run_summary.get("row_count", 0) <= 1:
        decision = "FAIL"
        reason = "CUDA/OOM failure prevented a usable Task100B artifact."
    elif failure:
        decision = "PARTIAL"
        reason = "Run artifact exists but contains CUDA/OOM failure flags."
    elif not metadata_ok:
        decision = "FAIL"
        reason = "Artifact metadata does not prove light compressor CUDA placement."
    elif not complete:
        decision = "PARTIAL"
        reason = "Run did not complete the required 100 measured rows."
    elif isinstance(strict_rate, float) and isinstance(task96_strict_rate, float) and strict_rate < task96_strict_rate - 0.10:
        decision = "PARTIAL"
        reason = "Strict calibrated proxy rate regressed beyond the bounded caveat threshold."
    elif isinstance(cap_rate, float) and isinstance(task96_cap_rate, float) and cap_rate > task96_cap_rate + 0.10:
        decision = "PARTIAL"
        reason = "Cap-limited rate increased beyond the bounded caveat threshold."
    elif isinstance(t_compress_delta, float) and t_compress_delta >= 0.0:
        decision = "PARTIAL"
        reason = "Compression overhead did not remain below the Task96 light CPU reference."
    elif isinstance(e2e_delta, float) and e2e_delta > 0.25:
        decision = "PARTIAL"
        reason = "End-to-end time was not favorable/stable relative to the Task96 light CPU reference."
    else:
        decision = "PASS_WITH_CAVEAT"
        reason = "Light GPU n100 completed with CUDA metadata, no OOM/CUDA flags, bounded proxy quality, and lower compression overhead."

    return {
        "decision": decision,
        "reason": reason,
        "next_step": "T100C_optimization_gap_analysis" if decision == "PASS_WITH_CAVEAT" else "keep_light_cpu_as_supported_path",
        "automatic_default_gpu_switch": False,
        "automatic_large_cpu_n100": False,
        "automatic_full_matrix": False,
        "automatic_qmsum": False,
        "keep_cpu_light_supported_path": True,
        "final_claims_allowed": False,
        "claim_boundary": {
            "no_final_speedup_claim": True,
            "no_final_quality_claim": True,
            "no_deployment_or_8gb_readiness_claim": True,
            "no_qmsum_semantic_correctness_claim": True,
            "no_full_benchmark_claim": True,
            "no_default_gpu_switch": True,
        },
        "diagnostics": {
            "task99r_row_count": task99r_reference.get("row_count", task99r_reference.get("n")),
            "task96_light_strict_rate": task96_strict_rate,
            "task96_light_cap_limited_rate": task96_cap_rate,
            "strict_rate_delta_vs_task96_light": (
                round(strict_rate - task96_strict_rate, 6)
                if isinstance(strict_rate, float) and isinstance(task96_strict_rate, float)
                else None
            ),
            "cap_rate_delta_vs_task96_light": (
                round(cap_rate - task96_cap_rate, 6)
                if isinstance(cap_rate, float) and isinstance(task96_cap_rate, float)
                else None
            ),
            "avg_t_compress_ms_delta_vs_task96_light": t_compress_delta,
            "avg_e2e_time_s_delta_vs_task96_light": e2e_delta,
        },
    }


def analyze(
    *,
    run_artifact: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    task99r_summary: Path = DEFAULT_TASK99R_SUMMARY,
    task96_light_reference: Path = DEFAULT_TASK96_LIGHT,
    task96_large_reference: Path = DEFAULT_TASK96_LARGE,
    dflash_reference: Path | None = DEFAULT_DFLASH,
) -> dict[str, Any]:
    run_summary = summarize_light_gpu_run(run_artifact)
    task99r = load_reference(task99r_summary, role="bounded_gpu_reference")
    task96_light = load_reference(task96_light_reference, role="controlled_cpu_reference")
    task96_large = load_reference(task96_large_reference, role="controlled_cpu_reference")
    dflash = (
        load_reference(dflash_reference, role="historical_reference", historical_only=True)
        if dflash_reference is not None and dflash_reference.exists()
        else None
    )
    comparisons = build_reference_comparisons(
        run_summary=run_summary,
        task99r_reference=task99r,
        task96_light_reference=task96_light,
        task96_large_reference=task96_large,
        dflash_reference=dflash,
    )
    recommendation = build_recommendation(
        run_summary=run_summary,
        task99r_reference=task99r,
        task96_light_reference=task96_light,
    )
    summary = {
        "task": "Task100B",
        "decision": recommendation["decision"],
        "light_gpu_n100": run_summary,
        "references": {
            "task99r_light_gpu_n10": task99r,
            "task96_light_cpu_n30": task96_light,
            "task96_large_cpu_n30": task96_large,
            "dflash_r1_historical": dflash,
        },
        "comparisons": comparisons,
        "recommendation": recommendation,
        "forbidden_scope_confirmation": {
            "large_cpu_n100_run": False,
            "baseline_ar_run": False,
            "dflash_r1_run": False,
            "qmsum_run": False,
            "full_matrix_run": False,
            "keep_rate_tuning": False,
            "default_gpu_switch": False,
        },
    }
    summary_dir = output_dir / "summary"
    tables_dir = output_dir / "tables"
    _write_json(summary_dir / "task100b_light_gpu_n100_summary.json", summary)
    _write_json(summary_dir / "task100b_recommendation.json", recommendation)
    _write_json(summary_dir / "task100b_reference_comparison.json", comparisons)
    _write_jsonl(summary_dir / "task100b_row_labels.jsonl", run_summary["labels"])
    _write_csv(tables_dir / "task100b_light_gpu_n100_table.csv", _table_rows(summary))
    return summary


def _table_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    run = summary["light_gpu_n100"]
    rows = [
        {"section": "run", "label": "decision", "value": summary["decision"], "note": "Task100B"},
        {"section": "run", "label": "row_count", "value": run["row_count"], "note": "expected 100"},
        {"section": "run", "label": "strict_correct_count", "value": run["strict_correct_count"], "note": ""},
        {"section": "run", "label": "cap_limited_incomplete_count", "value": run["cap_limited_incomplete_count"], "note": ""},
        {"section": "run", "label": "final_answer_marker_count", "value": run["final_answer_marker_count"], "note": ""},
        {"section": "run", "label": "strict_wrong_numeric_count", "value": run["strict_wrong_numeric_count"], "note": ""},
        {"section": "run", "label": "avg_t_compress_ms", "value": _round2(run["avg_t_compress_ms"]), "note": ""},
        {"section": "run", "label": "avg_e2e_time_s", "value": _round2(run["avg_e2e_time_s"]), "note": ""},
        {"section": "run", "label": "avg_tokens_per_second", "value": _round2(run["avg_tokens_per_second"]), "note": ""},
        {"section": "run", "label": "avg_tau_mean", "value": _round2(run["avg_tau_mean"]), "note": ""},
        {"section": "run", "label": "avg_R_actual", "value": _round2(run["avg_R_actual"]), "note": ""},
        {"section": "run", "label": "max_vram_reserved_gib", "value": _round2(run["max_vram_reserved_gib"]), "note": ""},
        {"section": "metadata", "label": "compressor_profile", "value": run["compressor_profile"], "note": ""},
        {"section": "metadata", "label": "compressor_device_map", "value": run["compressor_device_map"], "note": ""},
        {"section": "metadata", "label": "requested_compressor_device_map", "value": run["requested_compressor_device_map"], "note": ""},
    ]
    for key, comparison in summary["comparisons"].items():
        rows.append(
            {
                "section": "comparison",
                "label": key,
                "value": comparison["comparison_class"],
                "note": comparison["caveat"],
            }
        )
    return rows


def _find_default_run(output_dir: Path) -> Path:
    run_dir = output_dir / "runs"
    matches = sorted(run_dir.glob(DEFAULT_RUN_GLOB))
    if not matches:
        raise FileNotFoundError(f"No Task100B run artifact matching {DEFAULT_RUN_GLOB} under {run_dir}")
    return matches[-1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze Task100B light GPU n100 controlled run artifacts.")
    parser.add_argument("--run-artifact", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--task99r-summary", type=Path, default=DEFAULT_TASK99R_SUMMARY)
    parser.add_argument("--task96-light-reference", type=Path, default=DEFAULT_TASK96_LIGHT)
    parser.add_argument("--task96-large-reference", type=Path, default=DEFAULT_TASK96_LARGE)
    parser.add_argument("--dflash-reference", type=Path, default=DEFAULT_DFLASH)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_artifact = args.run_artifact or _find_default_run(args.output_dir)
    analyze(
        run_artifact=run_artifact,
        output_dir=args.output_dir,
        task99r_summary=args.task99r_summary,
        task96_light_reference=args.task96_light_reference,
        task96_large_reference=args.task96_large_reference,
        dflash_reference=args.dflash_reference,
    )


if __name__ == "__main__":
    main()
