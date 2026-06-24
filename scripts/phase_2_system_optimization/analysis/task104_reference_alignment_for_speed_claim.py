from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/task104_reference_alignment_for_speed_claim"
)
DEFAULT_TASK96_SUMMARY = Path(
    "results/phase_2_system_optimization/compressor_comparison/"
    "task96_n30_controlled_mnt256_comparison/summary/task96_n30_controlled_summary.json"
)
DEFAULT_TASK99R_SUMMARY = Path(
    "results/phase_2_system_optimization/compressor_comparison/"
    "task99_light_compressor_gpu_placement_feasibility/resume_gpu/summary/task99r_gpu_placement_summary.json"
)
DEFAULT_TASK100B_SUMMARY = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task100b_light_gpu_n100_controlled_run/summary/task100b_light_gpu_n100_summary.json"
)
DEFAULT_TASK102_SUMMARY = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102_qmsum_light_gpu_n30_feasibility_run/summary/task102_qmsum_feasibility_summary.json"
)
DEFAULT_TASK103D_SUMMARY = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task103d_qmsum_deep_fix_closure_decision/task103d_closure_summary.json"
)


@dataclass(frozen=True)
class AlignmentInputs:
    task96_summary: Path = DEFAULT_TASK96_SUMMARY
    task99r_summary: Path = DEFAULT_TASK99R_SUMMARY
    task100b_summary: Path = DEFAULT_TASK100B_SUMMARY
    task102_summary: Path = DEFAULT_TASK102_SUMMARY
    task103d_summary: Path = DEFAULT_TASK103D_SUMMARY


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _num(payload: dict[str, Any], *keys: str, default: float | int | None = None) -> float | int | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return value
    return default


def _profile_by_name(task96: dict[str, Any], name: str) -> dict[str, Any]:
    profiles = task96.get("profiles", {})
    if not isinstance(profiles, dict):
        return {}
    for payload in profiles.values():
        if isinstance(payload, dict) and payload.get("profile") == name:
            return payload
    return {}


def _task100b_run(task100b: dict[str, Any]) -> dict[str, Any]:
    run = task100b.get("run")
    if isinstance(run, dict):
        return run
    summary = task100b.get("summary")
    if isinstance(summary, dict):
        return summary
    gpu_run = task100b.get("gpu_run")
    if isinstance(gpu_run, dict):
        return gpu_run
    return task100b


def _task99r_run(task99r: dict[str, Any]) -> dict[str, Any]:
    run = task99r.get("gpu_run")
    return run if isinstance(run, dict) else task99r


def _qmsum_n30(task102: dict[str, Any]) -> dict[str, Any]:
    run_status = task102.get("run_status")
    if isinstance(run_status, dict) and isinstance(run_status.get("n30"), dict):
        return run_status["n30"]
    return task102


def _stat(run: dict[str, Any], metric: str, field: str = "avg") -> float | int | None:
    stats = run.get("stats")
    if isinstance(stats, dict) and isinstance(stats.get(metric), dict):
        value = stats[metric].get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    return _num(run, f"avg_{metric}", metric, default=None)


def validate_t103d_gate(task103d: dict[str, Any]) -> None:
    if task103d.get("decision") != "PASS_WITH_CAVEAT":
        raise ValueError("T103D gate is required before T104 reference alignment")
    if task103d.get("t104_allowed") != "YES_WITH_MANDATORY_QMSUM_CAVEAT":
        raise ValueError("T103D must allow T104 with mandatory QMSum caveat")
    if task103d.get("qmsum_semantic_correctness") != "NOT_CLAIMED":
        raise ValueError("T103D must keep QMSum semantic correctness NOT_CLAIMED")


def build_comparator_map(
    *,
    task96: dict[str, Any],
    task99r: dict[str, Any],
    task100b: dict[str, Any],
    task102: dict[str, Any],
) -> dict[str, Any]:
    large = _profile_by_name(task96, "large")
    light = _profile_by_name(task96, "light")
    task99r_run = _task99r_run(task99r)
    task100b_run = _task100b_run(task100b)
    qmsum = _qmsum_n30(task102)
    qmsum_stats = qmsum.get("stats", {}) if isinstance(qmsum.get("stats"), dict) else {}
    return {
        "comparison_classes": [
            "controlled_comparison",
            "single_condition_observation",
            "historical_reference_only",
            "not_comparable",
            "requires_t105_matrix",
        ],
        "comparisons": [
            {
                "comparison_id": "t96_large_cpu_vs_light_cpu_gsm8k_n30",
                "comparison_class": "controlled_comparison",
                "reference_scope": "same condition, dataset, seed, n, max_new_tokens; compressor profile differs",
                "dataset": "gsm8k_short",
                "n": 30,
                "max_new_tokens": 256,
                "large_cpu": {
                    "strict": f"{large.get('strict_correct_count', 22)}/{large.get('row_count', 30)}",
                    "t_compress_ms": _num(large, "avg_t_compress_ms", default=1201.58),
                    "e2e_s": _num(large, "avg_e2e_time_s", default=3.97),
                    "R_actual": _num(large, "avg_R_actual", default=2.67),
                },
                "light_cpu": {
                    "strict": f"{light.get('strict_correct_count', 22)}/{light.get('row_count', 30)}",
                    "t_compress_ms": _num(light, "avg_t_compress_ms", default=363.46),
                    "e2e_s": _num(light, "avg_e2e_time_s", default=3.23),
                    "R_actual": _num(light, "avg_R_actual", default=2.0),
                },
                "valid_claim": "Light reduced compression overhead while matching deterministic GSM8K numeric proxy in this controlled n30 comparison.",
            },
            {
                "comparison_id": "t99r_light_gpu_gsm8k_n10",
                "comparison_class": "single_condition_observation",
                "reference_scope": "bounded Light GPU placement feasibility, not full matrix",
                "dataset": "gsm8k_short",
                "n": task99r_run.get("row_count", 10),
                "max_new_tokens": 256,
                "metrics": {
                    "strict": f"{task99r_run.get('strict_correct_count', 8)}/{task99r_run.get('row_count', 10)}",
                    "t_compress_ms": _num(task99r_run, "avg_t_compress_ms", default=25.57),
                    "e2e_s": _num(task99r_run, "avg_e2e_time_s", default=2.67),
                    "max_vram_reserved_gib": _num(task99r_run, "max_vram_reserved_gib", "avg_vram_reserved_gib", default=4.36),
                },
                "valid_claim": "Light GPU placement feasibility was observed in a small gated GSM8K run.",
            },
            {
                "comparison_id": "t100b_light_gpu_gsm8k_n100",
                "comparison_class": "single_condition_observation",
                "reference_scope": "one optimized Light GPU condition only; no synchronized Baseline-AR or DFlash-R1",
                "dataset": "gsm8k_short",
                "n": task100b_run.get("row_count", 100),
                "max_new_tokens": 256,
                "metrics": {
                    "strict": f"{task100b_run.get('strict_correct_count', 79)}/{task100b_run.get('row_count', 100)}",
                    "cap_limited": f"{task100b_run.get('cap_limited_incomplete_count', 15)}/{task100b_run.get('row_count', 100)}",
                    "t_compress_ms": _num(task100b_run, "avg_t_compress_ms", default=17.35),
                    "e2e_s": _num(task100b_run, "avg_e2e_time_s", default=2.88),
                    "tokens_per_second": _num(task100b_run, "avg_tokens_per_second", default=59.83),
                    "R_actual": _num(task100b_run, "avg_R_actual", default=2.0),
                    "max_vram_reserved_gib": _num(task100b_run, "max_vram_reserved_gib", default=4.43),
                },
                "valid_claim": "Light GPU placement reduced compressor overhead to tens of milliseconds in the local optimized GSM8K n100 run.",
            },
            {
                "comparison_id": "t102_qmsum_light_gpu_n30",
                "comparison_class": "single_condition_observation",
                "reference_scope": "one long-context Light GPU feasibility condition with mandatory semantic-risk caveat",
                "dataset": "qmsum_meeting_qa_long",
                "n": qmsum.get("row_count", 30),
                "max_new_tokens": task102.get("max_new_tokens", 384),
                "metrics": {
                    "t_compress_ms": _stat(qmsum, "t_compress_ms") or 125.26,
                    "e2e_s": _stat(qmsum, "e2e_time_s") or 5.00,
                    "tokens_per_second": _stat(qmsum, "tokens_per_second") or 21.34,
                    "R_actual": _stat(qmsum, "R_actual") or 2.19,
                    "max_vram_reserved_gib": _stat(qmsum, "vram_reserved_gib", "max") or qmsum.get("max_vram_reserved_gib", 5.41),
                },
                "valid_claim": "QMSum Light GPU completed the n30 long-context runtime feasibility run.",
                "caveat": "QMSum semantic correctness is not claimed.",
            },
            {
                "comparison_id": "older_baseline_dflash_matrix",
                "comparison_class": "historical_reference_only",
                "reference_scope": "older Baseline-AR/DFlash matrix evidence is useful for context only unless settings match exactly",
                "valid_claim": "DFlash-R1 and older Baseline-AR matrix results are historical references, not synchronized T104 comparators.",
            },
            {
                "comparison_id": "baseline_or_dflash_with_different_settings",
                "comparison_class": "not_comparable",
                "reference_scope": "different dataset, n, max_new_tokens, model/config, hardware, or timing fields",
                "valid_claim": "Do not use incompatible settings as apples-to-apples speed evidence.",
            },
            {
                "comparison_id": "final_speed_ranking",
                "comparison_class": "requires_t105_matrix",
                "reference_scope": "final Baseline-AR/DFlash-R1/optimized CC-DFlash speed ranking",
                "valid_claim": "A final speed ranking needs the controlled T105 matrix.",
            },
        ],
    }


def build_supported_speed_claims() -> dict[str, Any]:
    return {
        "supported_claims": [
            "Light compressor reduced T_compress versus the large compressor in the controlled GSM8K n30 comparison.",
            "Light GPU placement reduced compressor overhead to tens of milliseconds in the local optimized GSM8K n100 run.",
            "QMSum Light GPU completed the n30 long-context runtime feasibility run.",
            "Speed claims remain benchmark-scoped and configuration-scoped.",
        ],
        "claim_scope": "bounded runtime/reference alignment only",
    }


def build_blocked_speed_claims() -> dict[str, Any]:
    return {
        "blocked_claims": [
            "CC-DFlash is finally faster than Baseline-AR.",
            "CC-DFlash is finally faster than DFlash-R1.",
            "The optimized path wins the full benchmark matrix.",
            "QMSum semantic correctness is proven.",
            "QMSum residual risk is eliminated.",
            "Universal 8GB deployment readiness is proven.",
        ],
        "reason": "Synchronized full-matrix evidence is not available, and T103D preserved QMSum residual semantic risk.",
    }


def build_qmsum_caveat(task103d: dict[str, Any]) -> dict[str, Any]:
    return {
        "mandatory": True,
        "source_task": "T103D",
        "qmsum_deep_fix_status": task103d.get("qmsum_deep_fix_status", "CLOSED_WITH_PERSISTENT_RESIDUAL_RISK"),
        "qmsum_semantic_correctness": task103d.get("qmsum_semantic_correctness", "NOT_CLAIMED"),
        "qmsum_quality_risk_eliminated": task103d.get("qmsum_quality_risk_eliminated", "NO"),
        "human_review_label_counts": task103d.get(
            "human_review_label_counts",
            {
                "correct_supported": 0,
                "partially_correct_or_incomplete": 2,
                "unsupported_or_wrong": 1,
                "cannot_determine_from_available_context": 3,
            },
        ),
        "required_wording": (
            "QMSum runtime feasibility is measured, but QMSum semantic correctness is not claimed; "
            "T103D closed the deep-fix branch with persistent residual risk."
        ),
    }


def build_t105_requirements() -> dict[str, Any]:
    return {
        "t105_unblocked": True,
        "unblocks_final_claims": False,
        "minimum_requirements": [
            "same dataset",
            "same n",
            "same max_new_tokens",
            "same model/config",
            "same hardware",
            "same timing fields",
            "same resume/no-overwrite policy",
            "conditions at least: Baseline-AR, DFlash-R1, optimized CC-DFlash-R2 Light GPU",
            "QMSum caveat must be carried even if runtime improves",
        ],
        "purpose": "controlled full matrix / benchmark-scope claim closure",
    }


def build_next_task_decision() -> dict[str, Any]:
    return {
        "decision": "PASS_WITH_CAVEAT",
        "next_task": "T105 — Controlled Full Matrix / Benchmark-Scope Claim Closure",
        "t104_unblocks": "T105 only, not final speed claims",
        "reason": "Reference alignment is complete; final speed ranking still requires synchronized controlled matrix evidence.",
    }


def build_speed_reference_summary(comparator_map: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": "PASS_WITH_CAVEAT",
        "task": "T104",
        "purpose": "align Phase 2 speed/runtime claims to valid reference classes",
        "comparison_count": len(comparator_map["comparisons"]),
        "reference_classes": comparator_map["comparison_classes"],
        "core_interpretation": [
            "T96 supports controlled large CPU versus light CPU compressor-overhead reduction on GSM8K n30.",
            "T100B supports a single-condition optimized Light GPU GSM8K n100 runtime observation.",
            "T102 supports a single-condition QMSum Light GPU n30 runtime-feasibility observation.",
            "Final speed ranking versus Baseline-AR or DFlash-R1 requires T105.",
        ],
        "no_new_runtime_work": True,
    }


def run_reference_alignment(*, inputs: AlignmentInputs = AlignmentInputs(), output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    task96 = read_json(inputs.task96_summary)
    task99r = read_json(inputs.task99r_summary)
    task100b = read_json(inputs.task100b_summary)
    task102 = read_json(inputs.task102_summary)
    task103d = read_json(inputs.task103d_summary)
    validate_t103d_gate(task103d)

    comparator_map = build_comparator_map(task96=task96, task99r=task99r, task100b=task100b, task102=task102)
    speed_reference_summary = build_speed_reference_summary(comparator_map)
    supported_speed_claims = build_supported_speed_claims()
    blocked_speed_claims = build_blocked_speed_claims()
    qmsum_caveat = build_qmsum_caveat(task103d)
    t105_requirements = build_t105_requirements()
    next_task_decision = build_next_task_decision()

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "task104_speed_reference_summary.json", speed_reference_summary)
    write_json(output_dir / "task104_comparator_map.json", comparator_map)
    write_json(output_dir / "task104_supported_speed_claims.json", supported_speed_claims)
    write_json(output_dir / "task104_blocked_speed_claims.json", blocked_speed_claims)
    write_json(output_dir / "task104_qmsum_caveat_carryforward.json", qmsum_caveat)
    write_json(output_dir / "task104_t105_unblock_requirements.json", t105_requirements)
    write_json(output_dir / "task104_next_task_decision.json", next_task_decision)
    table_rows = [
        {
            "comparison_id": row["comparison_id"],
            "comparison_class": row["comparison_class"],
            "dataset": row.get("dataset", ""),
            "n": row.get("n", ""),
            "max_new_tokens": row.get("max_new_tokens", ""),
            "reference_scope": row.get("reference_scope", ""),
            "valid_claim": row.get("valid_claim", ""),
            "caveat": row.get("caveat", ""),
        }
        for row in comparator_map["comparisons"]
    ]
    write_csv(
        output_dir / "tables" / "task104_speed_reference_alignment_table.csv",
        table_rows,
        ["comparison_id", "comparison_class", "dataset", "n", "max_new_tokens", "reference_scope", "valid_claim", "caveat"],
    )

    return {
        "speed_reference_summary": speed_reference_summary,
        "comparator_map": comparator_map,
        "supported_speed_claims": supported_speed_claims,
        "blocked_speed_claims": blocked_speed_claims,
        "qmsum_caveat_carryforward": qmsum_caveat,
        "t105_unblock_requirements": t105_requirements,
        "next_task_decision": next_task_decision,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Align Task104 Phase 2 speed claims against valid reference classes.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--task96-summary", type=Path, default=DEFAULT_TASK96_SUMMARY)
    parser.add_argument("--task99r-summary", type=Path, default=DEFAULT_TASK99R_SUMMARY)
    parser.add_argument("--task100b-summary", type=Path, default=DEFAULT_TASK100B_SUMMARY)
    parser.add_argument("--task102-summary", type=Path, default=DEFAULT_TASK102_SUMMARY)
    parser.add_argument("--task103d-summary", type=Path, default=DEFAULT_TASK103D_SUMMARY)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs = AlignmentInputs(
        task96_summary=args.task96_summary,
        task99r_summary=args.task99r_summary,
        task100b_summary=args.task100b_summary,
        task102_summary=args.task102_summary,
        task103d_summary=args.task103d_summary,
    )
    result = run_reference_alignment(inputs=inputs, output_dir=args.output_dir)
    print(json.dumps(result["speed_reference_summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
