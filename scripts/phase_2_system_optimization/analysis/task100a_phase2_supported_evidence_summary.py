from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/task100a_phase2_supported_evidence_summary"
)
DEFAULT_TASK96_SUMMARY = Path(
    "results/phase_2_system_optimization/compressor_comparison/"
    "task96_n30_controlled_mnt256_comparison/summary/task96_n30_controlled_summary.json"
)
DEFAULT_TASK99R_SUMMARY = Path(
    "results/phase_2_system_optimization/compressor_comparison/"
    "task99_light_compressor_gpu_placement_feasibility/resume_gpu/summary/"
    "task99r_gpu_placement_summary.json"
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _metric(row: dict[str, Any], key: str, default: Any = None) -> Any:
    return row.get(key, default)


def _ratio(correct: Any, total: Any) -> str:
    return f"{int(correct)}/{int(total)}"


def _round2(value: Any) -> Any:
    return round(float(value), 2) if isinstance(value, (int, float)) and not isinstance(value, bool) else value


def _task96_profile(task96: dict[str, Any], key: str) -> dict[str, Any]:
    try:
        return dict(task96["profiles"][key])
    except KeyError as exc:
        raise KeyError(f"Task96 summary missing profile {key!r}") from exc


def _supported_light_cpu(task96: dict[str, Any]) -> dict[str, Any]:
    profile = _task96_profile(task96, "seed42_light_n30_mnt256")
    return {
        "name": "CC-DFlash-R2 Light CPU",
        "evidence_source": "Task96",
        "dataset": "gsm8k_short",
        "n": int(_metric(profile, "row_count")),
        "max_new_tokens": 256,
        "strict": _ratio(profile["strict_correct_count"], profile["row_count"]),
        "cap_limited": _ratio(profile["cap_limited_incomplete_count"], profile["row_count"]),
        "t_compress_ms": _round2(profile["avg_t_compress_ms"]),
        "e2e_s": _round2(profile["avg_e2e_time_s"]),
        "R_actual": _round2(profile["avg_R_actual"]),
        "status": "supported controlled Phase 2 CPU path",
        "preferred_cpu_path": True,
    }


def _large_cpu_reference(task96: dict[str, Any]) -> dict[str, Any]:
    profile = _task96_profile(task96, "seed42_large_n30_mnt256")
    return {
        "name": "CC-DFlash-R2 Large CPU",
        "evidence_source": "Task96",
        "dataset": "gsm8k_short",
        "n": int(_metric(profile, "row_count")),
        "max_new_tokens": 256,
        "strict": _ratio(profile["strict_correct_count"], profile["row_count"]),
        "cap_limited": _ratio(profile["cap_limited_incomplete_count"], profile["row_count"]),
        "t_compress_ms": _round2(profile["avg_t_compress_ms"]),
        "e2e_s": _round2(profile["avg_e2e_time_s"]),
        "R_actual": _round2(profile["avg_R_actual"]),
        "status": "superseded as preferred optimization candidate; retained as historical/control reference",
        "retained_as_reference": True,
        "invalidated": False,
    }


def _light_gpu_candidate(task99r: dict[str, Any]) -> dict[str, Any]:
    gpu = dict(task99r["gpu_run"])
    return {
        "name": "CC-DFlash-R2 Light GPU",
        "evidence_source": "Task99-R",
        "dataset": "gsm8k_short",
        "n": int(gpu["row_count"]),
        "max_new_tokens": 256,
        "strict": _ratio(gpu["strict_correct_count"], gpu["row_count"]),
        "cap_limited": _ratio(gpu["cap_limited_incomplete_count"], gpu["row_count"]),
        "t_compress_ms": _round2(gpu["avg_t_compress_ms"]),
        "e2e_s": _round2(gpu["avg_e2e_time_s"]),
        "R_actual": _round2(gpu.get("avg_R_actual")),
        "avg_vram_reserved_gib": _round2(gpu.get("avg_vram_reserved_gib")),
        "tokens_per_second": _round2(gpu.get("avg_tokens_per_second")),
        "compressor_profile": gpu.get("compressor_profile"),
        "compressor_device_map": gpu.get("compressor_device_map"),
        "requested_compressor_device_map": gpu.get("requested_compressor_device_map"),
        "local_files_only": True,
        "oom_or_cuda_failure": bool(gpu.get("failure_flags", {}).get("oom_or_cuda_failure")),
        "status": "promising bounded candidate, not default, not deployment-ready",
        "is_default": False,
        "deployment_ready": False,
    }


def _dflash_reference(task99r: dict[str, Any]) -> dict[str, Any]:
    reference = dict(task99r.get("references", {}).get("dflash_historical") or {})
    return {
        "name": "DFlash-R1",
        "evidence_source": reference.get("source_task", "Task88"),
        "condition": reference.get("condition", "DFlash-R1"),
        "status": "historical-only reference",
        "historical_only": True,
        "n": reference.get("row_count") or reference.get("n"),
        "max_new_tokens": reference.get("max_new_tokens"),
        "note": "Task88 max_new_tokens/settings differ; not apples-to-apples with Task99-R.",
    }


def _claim_language() -> dict[str, list[str]]:
    return {
        "allowed": [
            "The light CPU compressor path is the supported controlled Phase 2 result.",
            "The light GPU placement path is a promising bounded candidate.",
            "In controlled GSM8K mnt256 n30, light CPU matched large CPU on calibrated strict proxy and reduced t_compress/e2e.",
            "In bounded n10, light GPU placement further reduced t_compress without observed OOM in that run.",
        ],
        "blocked": [
            "Light GPU is the default.",
            "Large CPU is invalid.",
            "Final speedup is proven.",
            "Final quality is proven.",
            "Deployment readiness is proven.",
            "8GB deployment readiness is confirmed.",
            "QMSum semantic correctness is proven.",
            "n100 is already completed.",
            "DFlash-R1 is broken.",
        ],
    }


def _next_step_plan() -> dict[str, Any]:
    return {
        "next_gated_task": "T100B — Light GPU n100 Controlled Run",
        "purpose": "Scale the promising light GPU candidate to n100 GSM8K mnt256.",
        "scope": {
            "condition": "CC-DFlash-R2",
            "compressor_profile": "light",
            "compressor_device_map": "cuda",
            "dataset": "gsm8k_short",
            "max_new_tokens": 256,
            "n": 100,
        },
        "blocked_actions": {
            "large_cpu_n100": True,
            "baseline_ar": True,
            "dflash_r1": True,
            "full_matrix": True,
            "qmsum": True,
            "keep_rate_tuning": True,
        },
        "framing": {
            "not_full_matrix": True,
            "not_final_benchmark": True,
            "scale_up_validation_only": True,
            "task96_cpu_references_remain_reference_evidence": True,
        },
    }


def _candidate_status(light_cpu: dict[str, Any], large_cpu: dict[str, Any], light_gpu: dict[str, Any]) -> dict[str, Any]:
    return {
        "light_cpu": {
            "status": light_cpu["status"],
            "supported_controlled_result": True,
            "preferred_cpu_path": True,
        },
        "large_cpu": {
            "status": large_cpu["status"],
            "retained_as_reference": True,
            "deleted_or_invalid": False,
        },
        "light_gpu": {
            "status": light_gpu["status"],
            "promising_bounded_candidate": True,
            "is_default": False,
            "deployment_ready": False,
        },
    }


def analyze(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    task96_summary: Path = DEFAULT_TASK96_SUMMARY,
    task99r_summary: Path = DEFAULT_TASK99R_SUMMARY,
) -> dict[str, Any]:
    task96 = _read_json(task96_summary)
    task99r = _read_json(task99r_summary)

    light_cpu = _supported_light_cpu(task96)
    large_cpu = _large_cpu_reference(task96)
    light_gpu = _light_gpu_candidate(task99r)
    dflash = _dflash_reference(task99r)
    claim_language = _claim_language()
    next_step_plan = _next_step_plan()
    candidate_status = _candidate_status(light_cpu, large_cpu, light_gpu)

    summary = {
        "task": "Task100A",
        "decision": "PASS",
        "purpose": "Summarize supported Phase 2 evidence after Task99-R and prepare the gated T100B plan.",
        "evidence_classes": {
            "supported_controlled_result": light_cpu,
            "historical_control_reference": large_cpu,
            "promising_bounded_candidate": light_gpu,
            "historical_dflash_reference": dflash,
        },
        "claim_boundary": {
            "no_final_speedup_claim": True,
            "no_final_quality_claim": True,
            "no_deployment_or_8gb_readiness_claim": True,
            "no_qmsum_semantic_correctness_claim": True,
            "no_full_benchmark_claim": True,
        },
        "next_step": next_step_plan["next_gated_task"],
    }

    table_rows = [
        {
            "profile_path": light_cpu["name"],
            "source_task": light_cpu["evidence_source"],
            "n": light_cpu["n"],
            "mnt": light_cpu["max_new_tokens"],
            "strict_proxy": light_cpu["strict"],
            "cap_limited": light_cpu["cap_limited"],
            "t_compress_ms": light_cpu["t_compress_ms"],
            "e2e_s": light_cpu["e2e_s"],
            "R_actual": light_cpu["R_actual"],
            "status": light_cpu["status"],
        },
        {
            "profile_path": large_cpu["name"],
            "source_task": large_cpu["evidence_source"],
            "n": large_cpu["n"],
            "mnt": large_cpu["max_new_tokens"],
            "strict_proxy": large_cpu["strict"],
            "cap_limited": large_cpu["cap_limited"],
            "t_compress_ms": large_cpu["t_compress_ms"],
            "e2e_s": large_cpu["e2e_s"],
            "R_actual": large_cpu["R_actual"],
            "status": large_cpu["status"],
        },
        {
            "profile_path": light_gpu["name"],
            "source_task": light_gpu["evidence_source"],
            "n": light_gpu["n"],
            "mnt": light_gpu["max_new_tokens"],
            "strict_proxy": light_gpu["strict"],
            "cap_limited": light_gpu["cap_limited"],
            "t_compress_ms": light_gpu["t_compress_ms"],
            "e2e_s": light_gpu["e2e_s"],
            "R_actual": light_gpu["R_actual"],
            "status": light_gpu["status"],
        },
        {
            "profile_path": dflash["name"],
            "source_task": dflash["evidence_source"],
            "n": dflash["n"],
            "mnt": dflash["max_new_tokens"],
            "strict_proxy": "",
            "cap_limited": "",
            "t_compress_ms": "",
            "e2e_s": "",
            "R_actual": "",
            "status": dflash["status"],
        },
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "task100a_supported_evidence_summary.json", summary)
    _write_csv(output_dir / "task100a_supported_evidence_table.csv", table_rows)
    _write_json(output_dir / "task100a_candidate_status.json", candidate_status)
    _write_json(output_dir / "task100a_next_step_plan.json", next_step_plan)
    _write_json(output_dir / "task100a_claim_language.json", claim_language)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Package Task100A Phase 2 supported evidence summary.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--task96-summary", type=Path, default=DEFAULT_TASK96_SUMMARY)
    parser.add_argument("--task99r-summary", type=Path, default=DEFAULT_TASK99R_SUMMARY)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    analyze(output_dir=args.output_dir, task96_summary=args.task96_summary, task99r_summary=args.task99r_summary)


if __name__ == "__main__":
    main()
