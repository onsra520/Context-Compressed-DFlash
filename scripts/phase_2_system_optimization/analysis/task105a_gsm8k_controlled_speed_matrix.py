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
    "task105a_gsm8k_controlled_speed_matrix"
)
DEFAULT_RUN_DIR = DEFAULT_OUTPUT_DIR / "runs"
DEFAULT_BASELINE = DEFAULT_RUN_DIR / "baseline_ar_gsm8k_short_seed42_n100_mnt256.jsonl"
DEFAULT_DFLASH = DEFAULT_RUN_DIR / "dflash_r1_gsm8k_short_seed42_n100_mnt256.jsonl"
DEFAULT_OPTIMIZED = DEFAULT_RUN_DIR / "cc_dflash_r2_light_gpu_gsm8k_short_seed42_n100_mnt256.jsonl"

LABELS = (
    "strict_correct",
    "strict_wrong_numeric",
    "cap_limited_incomplete",
    "format_or_extraction_sensitive",
    "answer_missing",
    "proxy_uncertain",
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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        rows = [{"condition": "", "metric": "", "value": ""}]
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
    return round(mean(nums), 6) if nums else None


def _min(values: list[float | None]) -> float | None:
    nums = _numbers(values)
    return round(min(nums), 6) if nums else None


def _max(values: list[float | None]) -> float | None:
    nums = _numbers(values)
    return round(max(nums), 6) if nums else None


def _rate(count: int, total: int) -> float | None:
    return round(count / total, 6) if total else None


def _e2e_time(row: dict[str, Any]) -> float | None:
    direct = _numeric(row, "e2e_time_s", "end_to_end_time_s")
    if direct is not None:
        return direct
    generation = _numeric(row, "generation_time_s")
    if generation is None:
        return None
    return generation + ((_numeric(row, "t_compress_ms") or 0.0) / 1000.0)


def _stats(rows: list[dict[str, Any]], metric: str, *keys: str) -> dict[str, float | None]:
    values = [_numeric(row, *keys) for row in rows]
    return {
        f"avg_{metric}": _avg(values),
        f"min_{metric}": _min(values),
        f"max_{metric}": _max(values),
    }


def _failure_flags(rows: list[dict[str, Any]]) -> dict[str, Any]:
    messages: list[str] = []
    for row in rows:
        for key, value in row.items():
            lowered = str(key).lower()
            if not any(token in lowered for token in ("failure", "error", "oom", "cuda")):
                continue
            if value in (None, "", False):
                continue
            messages.append(f"{key}={value}")
    lowered_messages = [message.lower() for message in messages]
    return {
        "messages": messages,
        "oom_or_cuda_failure": any("oom" in message or "cuda" in message for message in lowered_messages),
    }


def _values(rows: list[dict[str, Any]], key: str) -> list[str]:
    return sorted({str(row.get(key)) for row in rows if row.get(key) not in (None, "")})


def _metadata_ok(rows: list[dict[str, Any]], *, expected_condition: str, optimized: bool, expected_n: int) -> bool:
    if len(rows) != expected_n:
        return False
    for row in rows:
        if row.get("condition") != expected_condition:
            return False
        if row.get("dataset_name") != "gsm8k_short":
            return False
        if row.get("prompt_source") != "dataset":
            return False
        if row.get("max_new_tokens") != 256:
            return False
        if optimized:
            if row.get("compressor_profile") != "light":
                return False
            if str(row.get("compressor_device_map")) not in {"cuda", "cuda:0"}:
                return False
            if str(row.get("requested_compressor_device_map")) not in {"cuda", "cuda:0"}:
                return False
            if row.get("local_files_only") is not True:
                return False
    return True


def _summarize_condition(
    *,
    label: str,
    expected_condition: str,
    path: Path,
    expected_n: int,
    optimized: bool = False,
) -> dict[str, Any]:
    rows = load_jsonl(path)
    labels = [
        t95b.calibrate_row(row, profile=label, row_index=index, artifact=path)
        for index, row in enumerate(rows, start=1)
    ]
    label_counts = {
        label_name: sum(1 for item in labels if item.get("calibrated_label") == label_name)
        for label_name in LABELS
    }
    e2e_values = [_e2e_time(row) for row in rows]
    flags = _failure_flags(rows)
    strict_correct = sum(1 for item in labels if item.get("strict_correct"))
    summary: dict[str, Any] = {
        "condition": label,
        "repo_condition": expected_condition,
        "artifact": str(path),
        "row_count": len(rows),
        "expected_row_count": expected_n,
        "row_count_ok": len(rows) == expected_n,
        "metadata_ok": _metadata_ok(rows, expected_condition=expected_condition, optimized=optimized, expected_n=expected_n),
        "dataset_names": _values(rows, "dataset_name"),
        "prompt_sources": _values(rows, "prompt_source"),
        "max_new_tokens_values": _values(rows, "max_new_tokens"),
        "strict_correct_count": strict_correct,
        "strict_correct_rate": _rate(strict_correct, len(rows)),
        "cap_limited_incomplete_count": label_counts["cap_limited_incomplete"],
        "cap_limited_incomplete_rate": _rate(label_counts["cap_limited_incomplete"], len(rows)),
        "strict_wrong_numeric_count": label_counts["strict_wrong_numeric"],
        "answer_missing_count": label_counts["answer_missing"],
        "proxy_uncertain_count": label_counts["proxy_uncertain"],
        "format_or_extraction_sensitive_count": label_counts["format_or_extraction_sensitive"],
        "final_answer_marker_count": sum(1 for item in labels if item.get("final_answer_marker_present")),
        "exact_containment_diagnostic_count": sum(1 for item in labels if item.get("exact_containment")),
        "invalid_or_empty_output_count": sum(
            1
            for row in rows
            if not isinstance(row.get("generated_text"), str) or not row.get("generated_text", "").strip()
        ),
        "calibrated_label_counts": label_counts,
        "failure_flags": flags,
        "oom_or_cuda_failure": flags["oom_or_cuda_failure"],
        "avg_e2e_time_s": _avg(e2e_values),
        "min_e2e_time_s": _min(e2e_values),
        "max_e2e_time_s": _max(e2e_values),
        "fixture_ids": [str(row.get("fixture_id") or row.get("dataset_id") or row.get("prompt_id")) for row in rows],
    }
    summary.update(_stats(rows, "generation_time_s", "generation_time_s"))
    summary.update(_stats(rows, "tokens_per_second", "tokens_per_second", "tok_per_sec"))
    summary.update(_stats(rows, "tau_mean", "tau_mean"))
    summary.update(_stats(rows, "t_prefill_ms", "t_prefill_ms"))
    summary.update(_stats(rows, "t_compress_ms", "t_compress_ms"))
    summary.update(_stats(rows, "R_actual", "R_actual", "actual_compression_ratio", "compression_ratio"))
    summary.update(_stats(rows, "vram_allocated_gib", "vram_allocated_gib"))
    summary.update(_stats(rows, "vram_reserved_gib", "vram_reserved_gib"))
    summary.update(_stats(rows, "prefill_vram_allocated_gib", "prefill_vram_allocated_gib"))
    summary.update(_stats(rows, "prefill_vram_reserved_gib", "prefill_vram_reserved_gib"))
    summary.update(_stats(rows, "output_tokens", "output_tokens", "generated_token_count"))
    if optimized:
        summary.update(
            {
                "compressor_profiles": _values(rows, "compressor_profile"),
                "compressor_device_maps": _values(rows, "compressor_device_map"),
                "requested_compressor_device_maps": _values(rows, "requested_compressor_device_map"),
                "local_files_only_values": _values(rows, "local_files_only"),
                "compressor_paths_present": all(bool(row.get("compressor_path")) for row in rows),
                "resolved_compressor_paths_present": all(bool(row.get("resolved_compressor_path")) for row in rows),
            }
        )
    return summary


def _delta(left: dict[str, Any], right: dict[str, Any], field: str) -> float | int | None:
    lhs = left.get(field)
    rhs = right.get(field)
    if isinstance(lhs, (int, float)) and isinstance(rhs, (int, float)):
        value = lhs - rhs
        return round(value, 6) if isinstance(value, float) else value
    return None


def _speed_comparison(optimized: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    optimized_e2e = optimized.get("avg_e2e_time_s")
    reference_e2e = reference.get("avg_e2e_time_s")
    e2e_delta = _delta(optimized, reference, "avg_e2e_time_s")
    percent_lower: float | None = None
    if isinstance(optimized_e2e, (int, float)) and isinstance(reference_e2e, (int, float)) and reference_e2e > 0:
        percent_lower = round((reference_e2e - optimized_e2e) / reference_e2e * 100.0, 6)
    return {
        "reference_condition": reference["condition"],
        "optimized_avg_e2e_time_s": optimized_e2e,
        "reference_avg_e2e_time_s": reference_e2e,
        "avg_e2e_time_s_delta_optimized_minus_reference": e2e_delta,
        "optimized_percent_lower_e2e_time": percent_lower,
        "optimized_faster_on_avg_e2e": isinstance(e2e_delta, (int, float)) and e2e_delta < 0,
        "strict_correct_delta": _delta(optimized, reference, "strict_correct_count"),
        "strict_correct_rate_delta": _delta(optimized, reference, "strict_correct_rate"),
        "cap_limited_delta": _delta(optimized, reference, "cap_limited_incomplete_count"),
        "tok_per_sec_delta": _delta(optimized, reference, "avg_tokens_per_second"),
    }


def _speed_ranking(conditions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(
        conditions.values(),
        key=lambda item: (
            item.get("avg_e2e_time_s") is None,
            item.get("avg_e2e_time_s") if item.get("avg_e2e_time_s") is not None else float("inf"),
        ),
    )
    return {
        "ranking_metric": "avg_e2e_time_s",
        "lower_is_better": True,
        "ranked_conditions": [
            {
                "rank": index,
                "condition": item["condition"],
                "avg_e2e_time_s": item.get("avg_e2e_time_s"),
                "avg_generation_time_s": item.get("avg_generation_time_s"),
                "avg_t_compress_ms": item.get("avg_t_compress_ms"),
                "avg_tokens_per_second": item.get("avg_tokens_per_second"),
                "strict_correct_count": item.get("strict_correct_count"),
                "strict_correct_rate": item.get("strict_correct_rate"),
            }
            for index, item in enumerate(ranked, start=1)
        ],
    }


def _quality_proxy_summary(conditions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    optimized = conditions["CC-DFlash-R2 Light GPU"]
    references = [conditions["Baseline-AR"], conditions["DFlash-R1"]]
    best_reference_rate = max(
        [rate for rate in (item.get("strict_correct_rate") for item in references) if isinstance(rate, (int, float))],
        default=None,
    )
    optimized_rate = optimized.get("strict_correct_rate")
    quality_proxy_preserved = (
        isinstance(optimized_rate, (int, float))
        and isinstance(best_reference_rate, (int, float))
        and optimized_rate >= best_reference_rate - 0.05
    )
    return {
        "policy": "Task95B calibrated deterministic GSM8K numeric proxy",
        "qmsum_not_evaluated": True,
        "quality_proxy_preserved_against_best_reference_with_5pp_margin": quality_proxy_preserved,
        "best_reference_strict_correct_rate": best_reference_rate,
        "optimized_strict_correct_rate": optimized_rate,
        "conditions": {
            name: {
                "strict_correct_count": item["strict_correct_count"],
                "strict_correct_rate": item["strict_correct_rate"],
                "cap_limited_incomplete_count": item["cap_limited_incomplete_count"],
                "strict_wrong_numeric_count": item["strict_wrong_numeric_count"],
                "answer_missing_count": item["answer_missing_count"],
                "proxy_uncertain_count": item["proxy_uncertain_count"],
                "final_answer_marker_count": item["final_answer_marker_count"],
            }
            for name, item in conditions.items()
        },
    }


def _failure_or_resume_audit(conditions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    condition_audit = {
        name: {
            "artifact": item["artifact"],
            "row_count": item["row_count"],
            "expected_row_count": item["expected_row_count"],
            "row_count_ok": item["row_count_ok"],
            "metadata_ok": item["metadata_ok"],
            "oom_or_cuda_failure": item["oom_or_cuda_failure"],
            "failure_messages": item["failure_flags"]["messages"],
        }
        for name, item in conditions.items()
    }
    return {
        "conditions": condition_audit,
        "any_incomplete": any(not item["row_count_ok"] for item in condition_audit.values()),
        "any_metadata_mismatch": any(not item["metadata_ok"] for item in condition_audit.values()),
        "any_oom_or_cuda_failure": any(item["oom_or_cuda_failure"] for item in condition_audit.values()),
        "resume_needed_conditions": [
            name
            for name, item in condition_audit.items()
            if not item["row_count_ok"] or not item["metadata_ok"] or item["oom_or_cuda_failure"]
        ],
    }


def _claim_update(
    *,
    conditions: dict[str, dict[str, Any]],
    speed_ranking: dict[str, Any],
    quality: dict[str, Any],
    complete: bool,
) -> dict[str, Any]:
    optimized = conditions["CC-DFlash-R2 Light GPU"]
    baseline = conditions["Baseline-AR"]
    dflash = conditions["DFlash-R1"]
    comparisons = {
        "optimized_vs_baseline_ar": _speed_comparison(optimized, baseline),
        "optimized_vs_dflash_r1": _speed_comparison(optimized, dflash),
    }
    speed_wins = all(item["optimized_faster_on_avg_e2e"] for item in comparisons.values())
    quality_ok = quality["quality_proxy_preserved_against_best_reference_with_5pp_margin"] is True
    supported = complete and speed_wins and quality_ok
    blocked_claims = [
        "full_benchmark_speed_claim",
        "qmsum_semantic_correctness",
        "universal_8gb_deployment_readiness",
        "default_gpu_switch",
        "dflash_r1_broken_claim",
    ]
    if not quality_ok:
        blocked_claims.append("quality_proxy_regression")
    if not speed_wins:
        blocked_claims.append("controlled_gsm8k_speed_win")
    return {
        "bounded_gsm8k_speed_claim_supported": supported,
        "qmsum_caveat_carryforward": True,
        "qmsum_claim_status_from_t103d_t104": "SCOPED_WITH_HUMAN_REVIEWED_RESIDUAL_RISK",
        "allowed_claims": [
            "T105A is a controlled GSM8K-only n=100 speed/quality matrix over Baseline-AR, DFlash-R1, and CC-DFlash-R2 Light GPU.",
            "CC-DFlash-R2 Light GPU may be compared to Baseline-AR and DFlash-R1 only within this matched GSM8K_short seed42 mnt256 setup.",
            "QMSum residual semantic risk remains caveated from T103D/T104 and is not resolved by this GSM8K matrix.",
        ],
        "blocked_claims": blocked_claims,
        "comparisons": comparisons,
        "speed_ranking_metric": speed_ranking["ranking_metric"],
        "recommendation": (
            "Proceed to T105B for QMSum runtime/reference alignment with QMSum caveat carried forward."
            if complete
            else "Run T105A-R to resume or repair incomplete controlled GSM8K matrix artifacts."
        ),
    }


def _next_task_decision(complete: bool) -> dict[str, Any]:
    if complete:
        return {
            "next_task": "T105B — QMSum Controlled Runtime Matrix",
            "reason": "T105A completed all three controlled GSM8K n100 matrix conditions.",
            "no_automatic_full_matrix": True,
            "qmsum_caveat_carryforward": True,
        }
    return {
        "next_task": "T105A-R — GSM8K Controlled Speed Matrix Resume",
        "reason": "At least one T105A condition is incomplete, has metadata mismatch, or recorded OOM/CUDA failure.",
        "no_automatic_full_matrix": True,
        "qmsum_caveat_carryforward": True,
    }


def _table_rows(conditions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, item in conditions.items():
        rows.append(
            {
                "condition": name,
                "artifact": item["artifact"],
                "row_count": item["row_count"],
                "strict_correct_count": item["strict_correct_count"],
                "strict_correct_rate": item["strict_correct_rate"],
                "cap_limited_incomplete_count": item["cap_limited_incomplete_count"],
                "strict_wrong_numeric_count": item["strict_wrong_numeric_count"],
                "avg_e2e_time_s": item["avg_e2e_time_s"],
                "avg_generation_time_s": item["avg_generation_time_s"],
                "avg_t_compress_ms": item["avg_t_compress_ms"],
                "avg_tokens_per_second": item["avg_tokens_per_second"],
                "avg_tau_mean": item["avg_tau_mean"],
                "avg_R_actual": item["avg_R_actual"],
                "max_vram_reserved_gib": item["max_vram_reserved_gib"],
                "metadata_ok": item["metadata_ok"],
                "oom_or_cuda_failure": item["oom_or_cuda_failure"],
            }
        )
    return rows


def analyze(
    *,
    baseline_jsonl: Path = DEFAULT_BASELINE,
    dflash_jsonl: Path = DEFAULT_DFLASH,
    optimized_jsonl: Path = DEFAULT_OPTIMIZED,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    expected_n: int = 100,
) -> dict[str, Any]:
    conditions = {
        "Baseline-AR": _summarize_condition(
            label="Baseline-AR",
            expected_condition="Baseline-AR",
            path=baseline_jsonl,
            expected_n=expected_n,
        ),
        "DFlash-R1": _summarize_condition(
            label="DFlash-R1",
            expected_condition="DFlash-R1",
            path=dflash_jsonl,
            expected_n=expected_n,
        ),
        "CC-DFlash-R2 Light GPU": _summarize_condition(
            label="CC-DFlash-R2 Light GPU",
            expected_condition="CC-DFlash-R2",
            path=optimized_jsonl,
            expected_n=expected_n,
            optimized=True,
        ),
    }
    failure_audit = _failure_or_resume_audit(conditions)
    controlled_matrix_complete = not (
        failure_audit["any_incomplete"]
        or failure_audit["any_metadata_mismatch"]
        or failure_audit["any_oom_or_cuda_failure"]
    )
    ranking = _speed_ranking(conditions)
    quality = _quality_proxy_summary(conditions)
    claim_update = _claim_update(
        conditions=conditions,
        speed_ranking=ranking,
        quality=quality,
        complete=controlled_matrix_complete,
    )
    next_decision = _next_task_decision(controlled_matrix_complete)
    decision = "FAIL" if failure_audit["any_oom_or_cuda_failure"] else ("PASS_WITH_CAVEAT" if controlled_matrix_complete else "PARTIAL")
    summary = {
        "task": "T105A",
        "decision": decision,
        "purpose": "Controlled GSM8K speed/quality matrix for Baseline-AR, DFlash-R1, and optimized CC-DFlash-R2 Light GPU.",
        "scope": {
            "dataset": "gsm8k_short",
            "seed": 42,
            "n": expected_n,
            "max_new_tokens": 256,
            "qmsum_run": False,
            "full_matrix": False,
            "llm_judge": False,
        },
        "controlled_matrix_complete": controlled_matrix_complete,
        "conditions": conditions,
        "speed_ranking": ranking,
        "quality_proxy_summary": quality,
        "failure_or_resume_audit": failure_audit,
        "claim_update": claim_update,
        "next_task_decision": next_decision,
    }

    summary_dir = output_dir / "summary"
    tables_dir = output_dir / "tables"
    _write_json(summary_dir / "task105a_matrix_summary.json", summary)
    _write_json(summary_dir / "task105a_condition_metrics.json", conditions)
    _write_json(summary_dir / "task105a_speed_ranking.json", ranking)
    _write_json(summary_dir / "task105a_quality_proxy_summary.json", quality)
    _write_json(summary_dir / "task105a_failure_or_resume_audit.json", failure_audit)
    _write_json(summary_dir / "task105a_claim_update.json", claim_update)
    _write_json(summary_dir / "task105a_next_task_decision.json", next_decision)
    _write_csv(tables_dir / "task105a_gsm8k_controlled_speed_matrix.csv", _table_rows(conditions))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze Task105A controlled GSM8K speed matrix artifacts.")
    parser.add_argument("--baseline-jsonl", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--dflash-jsonl", type=Path, default=DEFAULT_DFLASH)
    parser.add_argument("--optimized-jsonl", type=Path, default=DEFAULT_OPTIMIZED)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--expected-n", type=int, default=100)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = analyze(
        baseline_jsonl=args.baseline_jsonl,
        dflash_jsonl=args.dflash_jsonl,
        optimized_jsonl=args.optimized_jsonl,
        output_dir=args.output_dir,
        expected_n=args.expected_n,
    )
    print(
        json.dumps(
            {
                "task": summary["task"],
                "decision": summary["decision"],
                "controlled_matrix_complete": summary["controlled_matrix_complete"],
                "next_task": summary["next_task_decision"]["next_task"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
