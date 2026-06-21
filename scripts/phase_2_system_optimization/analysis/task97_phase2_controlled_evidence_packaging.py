from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task97_phase2_controlled_evidence_packaging"
)

DEFAULT_INPUTS = {
    "task93": Path(
        "results/phase_2_system_optimization/compressor_integration/"
        "task93_lighter_compressor_integration/comparison_summary/"
        "task93_large_vs_light_smoke_summary.json"
    ),
    "task94": Path(
        "results/phase_2_system_optimization/compressor_comparison/"
        "task94_light_vs_large_compressor_controlled_comparison/summary/"
        "task94_large_vs_light_summary.json"
    ),
    "task95a": Path(
        "results/phase_2_system_optimization/quality_and_latency_audits/"
        "task95a_analysis_and_failure_row_audit/task95a_failure_taxonomy_summary.json"
    ),
    "task95b": Path(
        "results/phase_2_system_optimization/quality_and_latency_audits/"
        "task95b_quality_proxy_calibration/task95b_calibrated_quality_summary.json"
    ),
    "task95c": Path(
        "results/phase_2_system_optimization/quality_and_latency_audits/"
        "task95c_cap_tail_policy_triage/summary/task95c_cap_tail_summary.json"
    ),
    "task95c_r": Path(
        "results/phase_2_system_optimization/quality_and_latency_audits/"
        "task95c_cap_tail_policy_triage/resume_mnt256/summary/task95c_r_cap_tail_summary.json"
    ),
    "task95d": Path(
        "results/phase_2_system_optimization/quality_and_latency_audits/"
        "task95d_bounded_mnt256_confirmation/summary/"
        "task95d_bounded_confirmation_summary.json"
    ),
    "task96": Path(
        "results/phase_2_system_optimization/compressor_comparison/"
        "task96_n30_controlled_mnt256_comparison/summary/"
        "task96_n30_controlled_summary.json"
    ),
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _round(value: Any, digits: int = 2) -> Any:
    if isinstance(value, float):
        return round(value, digits)
    return value


def load_inputs(paths: dict[str, Path] | None = None) -> dict[str, dict[str, Any]]:
    resolved = paths or DEFAULT_INPUTS
    return {key: _read_json(path) for key, path in resolved.items()}


def build_evidence_summary(data: dict[str, dict[str, Any]]) -> dict[str, Any]:
    task93 = data["task93"]
    task94 = data["task94"]
    task95a = data["task95a"]
    task95b = data["task95b"]
    task95c = data["task95c"]
    task95c_r = data["task95c_r"]
    task95d = data["task95d"]
    task96 = data["task96"]

    task96_large = task96["profiles"]["seed42_large_n30_mnt256"]
    task96_light = task96["profiles"]["seed42_light_n30_mnt256"]

    supported_claims = [
        "light compressor is integrated through the real CC-DFlash runner",
        "in controlled GSM8K mnt256 comparisons, light matched large on calibrated strict proxy at n=30",
        "light reduced average t_compress_ms versus large in the controlled n=30 mnt256 setup",
        "light reduced average e2e time versus large in the controlled n=30 mnt256 setup",
        "mnt256 reduced cap-limited incompleteness relative to mnt128",
        "light compresses less aggressively than large: R_actual about 2.00 vs 2.67",
    ]
    blocked_claims = [
        "no final speedup claim",
        "no final quality claim",
        "no deployment or 8GB readiness claim",
        "no QMSum semantic correctness claim",
        "no full benchmark claim",
        "no automatic n100 authorization",
        "no claim that GPU compressor placement is better yet",
    ]

    evidence_chain = [
        {
            "task": "T93",
            "status": "PASS_WITH_CAVEAT",
            "finding": "Light compressor integration passed through the real runner and reduced smoke t_compress_ms versus large, with quality still unaudited.",
            "metrics": {
                "large_avg_t_compress_ms": _round(task93["profiles"]["large"]["avg_t_compress_ms"]),
                "light_avg_t_compress_ms": _round(task93["profiles"]["light"]["avg_t_compress_ms"]),
                "large_avg_R_actual": _round(task93["profiles"]["large"]["avg_R_actual"]),
                "light_avg_R_actual": _round(task93["profiles"]["light"]["avg_R_actual"]),
            },
        },
        {
            "task": "T94",
            "status": task94["comparison"]["decision"]["status"],
            "finding": "Controlled mnt128 n=10 showed light faster but weaker on the GSM8K numeric proxy.",
            "metrics": {
                "large_numeric_proxy": f'{task94["profiles"]["large"]["numeric_extraction_match_count"]}/{task94["profiles"]["large"]["rows"]}',
                "light_numeric_proxy": f'{task94["profiles"]["light"]["numeric_extraction_match_count"]}/{task94["profiles"]["light"]["rows"]}',
                "large_avg_t_compress_ms": _round(task94["profiles"]["large"]["avg_t_compress_ms"]),
                "light_avg_t_compress_ms": _round(task94["profiles"]["light"]["avg_t_compress_ms"]),
                "large_avg_e2e_time_s": _round(task94["profiles"]["large"]["avg_e2e_time_s"]),
                "light_avg_e2e_time_s": _round(task94["profiles"]["light"]["avg_e2e_time_s"]),
            },
        },
        {
            "task": "T95A",
            "status": "PASS",
            "finding": "Row-level audit isolated large_correct_light_wrong rows and pointed to cap/truncation and format sensitivity rather than generic corruption.",
            "metrics": {
                "large_correct_light_wrong": task95a["outcome_group_counts"]["large_correct_light_wrong"],
                "truncation_or_cap_issue": task95a["failure_taxonomy_counts"]["truncation_or_cap_issue"],
                "format_or_extraction_issue": task95a["failure_taxonomy_counts"]["format_or_extraction_issue"],
            },
        },
        {
            "task": "T95B",
            "status": "PASS",
            "finding": "Calibrated strict proxy kept the gap at mnt128 and showed proxy uncertainty was not the explanation; cap pressure became the main triage target.",
            "metrics": {
                "large_strict": f'{task95b["profiles"]["large"]["strict_correct_count"]}/{task95b["profiles"]["large"]["rows"]}',
                "light_strict": f'{task95b["profiles"]["light"]["strict_correct_count"]}/{task95b["profiles"]["light"]["rows"]}',
                "large_cap_limited": f'{task95b["profiles"]["large"]["cap_limited_count"]}/{task95b["profiles"]["large"]["rows"]}',
                "light_cap_limited": f'{task95b["profiles"]["light"]["cap_limited_count"]}/{task95b["profiles"]["light"]["rows"]}',
                "proxy_uncertainty_explains_gap": task95b["recommendation"]["proxy_uncertainty_explains_gap"],
            },
        },
        {
            "task": "T95C",
            "status": task95c["decision"],
            "finding": "Static cap audit completed, but the bounded mnt256 run stayed blocked by GPU visibility failure.",
            "metrics": {
                "large_mnt128_strict": f'{task95c["static_cap_audit"]["large"]["strict_calibrated_correct"]}/{task95c["static_cap_audit"]["large"]["rows"]}',
                "light_mnt128_strict": f'{task95c["static_cap_audit"]["light"]["strict_calibrated_correct"]}/{task95c["static_cap_audit"]["light"]["rows"]}',
                "gpu_cuda_available": task95c["gpu_gate"]["cuda_available"],
            },
        },
        {
            "task": "T95C-R",
            "status": "PASS_WITH_CAVEAT",
            "finding": "After GPU recovery, mnt256 repaired the bounded gap on seed42 while light stayed lower in t_compress_ms and e2e time.",
            "metrics": {
                "large_strict": f'{task95c_r["profiles"]["large_256"]["strict_correct_count"]}/{task95c_r["profiles"]["large_256"]["row_count"]}',
                "light_strict": f'{task95c_r["profiles"]["light_256"]["strict_correct_count"]}/{task95c_r["profiles"]["light_256"]["row_count"]}',
                "large_cap_limited": f'{task95c_r["profiles"]["large_256"]["cap_limited_incomplete_count"]}/{task95c_r["profiles"]["large_256"]["row_count"]}',
                "light_cap_limited": f'{task95c_r["profiles"]["light_256"]["cap_limited_incomplete_count"]}/{task95c_r["profiles"]["light_256"]["row_count"]}',
                "large_avg_t_compress_ms": _round(task95c_r["profiles"]["large_256"]["avg_t_compress_ms"]),
                "light_avg_t_compress_ms": _round(task95c_r["profiles"]["light_256"]["avg_t_compress_ms"]),
            },
        },
        {
            "task": "T95D",
            "status": "PASS_WITH_CAVEAT",
            "finding": "A second bounded seed43 confirmation with zero fixture overlap preserved the mnt256 pattern.",
            "metrics": {
                "fixture_overlap": f'{task95d["fixture_overlap"]["overlap_count"]}/{task95d["fixture_overlap"]["confirmation_count"]}',
                "large_strict": f'{task95d["profiles"]["seed43_large_256"]["strict_correct_count"]}/{task95d["profiles"]["seed43_large_256"]["row_count"]}',
                "light_strict": f'{task95d["profiles"]["seed43_light_256"]["strict_correct_count"]}/{task95d["profiles"]["seed43_light_256"]["row_count"]}',
                "large_cap_limited": f'{task95d["profiles"]["seed43_large_256"]["cap_limited_incomplete_count"]}/{task95d["profiles"]["seed43_large_256"]["row_count"]}',
                "light_cap_limited": f'{task95d["profiles"]["seed43_light_256"]["cap_limited_incomplete_count"]}/{task95d["profiles"]["seed43_light_256"]["row_count"]}',
            },
        },
        {
            "task": "T96",
            "status": "PASS_WITH_CAVEAT",
            "finding": "Controlled n=30 mnt256 confirmed that light matched large on calibrated strict proxy while remaining lower in compression overhead and e2e time.",
            "metrics": {
                "large_strict": f'{task96_large["strict_correct_count"]}/{task96_large["row_count"]}',
                "light_strict": f'{task96_light["strict_correct_count"]}/{task96_light["row_count"]}',
                "large_cap_limited": f'{task96_large["cap_limited_incomplete_count"]}/{task96_large["row_count"]}',
                "light_cap_limited": f'{task96_light["cap_limited_incomplete_count"]}/{task96_light["row_count"]}',
                "large_avg_t_compress_ms": _round(task96_large["avg_t_compress_ms"]),
                "light_avg_t_compress_ms": _round(task96_light["avg_t_compress_ms"]),
                "large_avg_e2e_time_s": _round(task96_large["avg_e2e_time_s"]),
                "light_avg_e2e_time_s": _round(task96_light["avg_e2e_time_s"]),
                "large_avg_R_actual": _round(task96_large["avg_R_actual"]),
                "light_avg_R_actual": _round(task96_light["avg_R_actual"]),
            },
        },
    ]

    return {
        "task": "Task97",
        "decision": "PASS",
        "scope": "Packaging, planning, and UI repair only. No benchmark, model inference, or GPU work performed.",
        "evidence_chain": evidence_chain,
        "main_controlled_result": {
            "task": "T96",
            "condition": "CC-DFlash-R2",
            "dataset": "gsm8k_short",
            "seed": 42,
            "n": 30,
            "max_new_tokens": 256,
            "large": {
                "strict_correct": f'{task96_large["strict_correct_count"]}/{task96_large["row_count"]}',
                "cap_limited_incomplete": f'{task96_large["cap_limited_incomplete_count"]}/{task96_large["row_count"]}',
                "avg_t_compress_ms": _round(task96_large["avg_t_compress_ms"]),
                "avg_e2e_time_s": _round(task96_large["avg_e2e_time_s"]),
                "avg_R_actual": _round(task96_large["avg_R_actual"]),
            },
            "light": {
                "strict_correct": f'{task96_light["strict_correct_count"]}/{task96_light["row_count"]}',
                "cap_limited_incomplete": f'{task96_light["cap_limited_incomplete_count"]}/{task96_light["row_count"]}',
                "avg_t_compress_ms": _round(task96_light["avg_t_compress_ms"]),
                "avg_e2e_time_s": _round(task96_light["avg_e2e_time_s"]),
                "avg_R_actual": _round(task96_light["avg_R_actual"]),
            },
        },
        "interpretation": {
            "summary": [
                "Light compressor is promising under controlled GSM8K mnt256.",
                "The mnt128 quality drop was largely cap/tail-policy driven rather than explained by proxy uncertainty.",
                "Light trades less aggressive compression for much lower compression overhead.",
                "The evidence remains bounded deterministic proxy evidence only.",
            ]
        },
        "supported_bounded_claims": supported_claims,
        "blocked_claims": blocked_claims,
        "recommended_next_tasks": [
            "T98 optional n100 go/no-go decision",
            "T99 light compressor GPU placement feasibility",
        ],
        "source_artifacts": {key: str(path) for key, path in DEFAULT_INPUTS.items()},
    }


def build_evidence_table(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    task94 = data["task94"]
    task95b = data["task95b"]
    task95c = data["task95c"]
    task95c_r = data["task95c_r"]
    task95d = data["task95d"]
    task96 = data["task96"]

    rows = [
        {
            "task": "T93",
            "status": "PASS_WITH_CAVEAT",
            "sample": "n=3 smoke, seed42",
            "setting": "CC-DFlash-R2 / gsm8k_short / mnt128-equivalent smoke",
            "large_strict_proxy": "",
            "light_strict_proxy": "",
            "large_cap_limited": "",
            "light_cap_limited": "",
            "large_t_compress_ms": _round(data["task93"]["profiles"]["large"]["avg_t_compress_ms"]),
            "light_t_compress_ms": _round(data["task93"]["profiles"]["light"]["avg_t_compress_ms"]),
            "large_e2e_s": "",
            "light_e2e_s": "",
            "large_r_actual": _round(data["task93"]["profiles"]["large"]["avg_R_actual"]),
            "light_r_actual": _round(data["task93"]["profiles"]["light"]["avg_R_actual"]),
            "key_takeaway": "Integration passed and light reduced compression time in smoke only.",
        },
        {
            "task": "T94",
            "status": task94["comparison"]["decision"]["status"],
            "sample": "n=10, seed42",
            "setting": "CC-DFlash-R2 / gsm8k_short / max_new_tokens=128",
            "large_strict_proxy": f'{task94["profiles"]["large"]["numeric_extraction_match_count"]}/{task94["profiles"]["large"]["rows"]}',
            "light_strict_proxy": f'{task94["profiles"]["light"]["numeric_extraction_match_count"]}/{task94["profiles"]["light"]["rows"]}',
            "large_cap_limited": "",
            "light_cap_limited": "",
            "large_t_compress_ms": _round(task94["profiles"]["large"]["avg_t_compress_ms"]),
            "light_t_compress_ms": _round(task94["profiles"]["light"]["avg_t_compress_ms"]),
            "large_e2e_s": _round(task94["profiles"]["large"]["avg_e2e_time_s"]),
            "light_e2e_s": _round(task94["profiles"]["light"]["avg_e2e_time_s"]),
            "large_r_actual": _round(task94["profiles"]["large"]["avg_R_actual"]),
            "light_r_actual": _round(task94["profiles"]["light"]["avg_R_actual"]),
            "key_takeaway": "Light was faster but looked worse under the bounded mnt128 numeric proxy.",
        },
        {
            "task": "T95B",
            "status": "PASS",
            "sample": "calibration of T94 rows",
            "setting": "deterministic proxy calibration / mnt128",
            "large_strict_proxy": f'{task95b["profiles"]["large"]["strict_correct_count"]}/{task95b["profiles"]["large"]["rows"]}',
            "light_strict_proxy": f'{task95b["profiles"]["light"]["strict_correct_count"]}/{task95b["profiles"]["light"]["rows"]}',
            "large_cap_limited": f'{task95b["profiles"]["large"]["cap_limited_count"]}/{task95b["profiles"]["large"]["rows"]}',
            "light_cap_limited": f'{task95b["profiles"]["light"]["cap_limited_count"]}/{task95b["profiles"]["light"]["rows"]}',
            "large_t_compress_ms": "",
            "light_t_compress_ms": "",
            "large_e2e_s": "",
            "light_e2e_s": "",
            "large_r_actual": "",
            "light_r_actual": "",
            "key_takeaway": "Proxy uncertainty did not explain the gap; output-cap pressure became the triage target.",
        },
        {
            "task": "T95C",
            "status": task95c["decision"],
            "sample": "static audit only",
            "setting": "GPU blocked before bounded mnt256 rerun",
            "large_strict_proxy": f'{task95c["static_cap_audit"]["large"]["strict_calibrated_correct"]}/{task95c["static_cap_audit"]["large"]["rows"]}',
            "light_strict_proxy": f'{task95c["static_cap_audit"]["light"]["strict_calibrated_correct"]}/{task95c["static_cap_audit"]["light"]["rows"]}',
            "large_cap_limited": f'{task95c["static_cap_audit"]["large"]["cap_limited_incomplete"]}/{task95c["static_cap_audit"]["large"]["rows"]}',
            "light_cap_limited": f'{task95c["static_cap_audit"]["light"]["cap_limited_incomplete"]}/{task95c["static_cap_audit"]["light"]["rows"]}',
            "large_t_compress_ms": "",
            "light_t_compress_ms": "",
            "large_e2e_s": "",
            "light_e2e_s": "",
            "large_r_actual": "",
            "light_r_actual": "",
            "key_takeaway": "Static cap evidence justified mnt256, but the run stayed PARTIAL because CUDA was unavailable.",
        },
        {
            "task": "T95C-R",
            "status": "PASS_WITH_CAVEAT",
            "sample": "n=10, seed42",
            "setting": "CC-DFlash-R2 / gsm8k_short / max_new_tokens=256",
            "large_strict_proxy": f'{task95c_r["profiles"]["large_256"]["strict_correct_count"]}/{task95c_r["profiles"]["large_256"]["row_count"]}',
            "light_strict_proxy": f'{task95c_r["profiles"]["light_256"]["strict_correct_count"]}/{task95c_r["profiles"]["light_256"]["row_count"]}',
            "large_cap_limited": f'{task95c_r["profiles"]["large_256"]["cap_limited_incomplete_count"]}/{task95c_r["profiles"]["large_256"]["row_count"]}',
            "light_cap_limited": f'{task95c_r["profiles"]["light_256"]["cap_limited_incomplete_count"]}/{task95c_r["profiles"]["light_256"]["row_count"]}',
            "large_t_compress_ms": _round(task95c_r["profiles"]["large_256"]["avg_t_compress_ms"]),
            "light_t_compress_ms": _round(task95c_r["profiles"]["light_256"]["avg_t_compress_ms"]),
            "large_e2e_s": _round(task95c_r["profiles"]["large_256"]["avg_e2e_time_s"]),
            "light_e2e_s": _round(task95c_r["profiles"]["light_256"]["avg_e2e_time_s"]),
            "large_r_actual": _round(task95c_r["profiles"]["large_256"]["avg_R_actual"]),
            "light_r_actual": _round(task95c_r["profiles"]["light_256"]["avg_R_actual"]),
            "key_takeaway": "mnt256 repaired the bounded strict-proxy gap on seed42.",
        },
        {
            "task": "T95D",
            "status": "PASS_WITH_CAVEAT",
            "sample": "n=10, seed43",
            "setting": "CC-DFlash-R2 / gsm8k_short / max_new_tokens=256",
            "large_strict_proxy": f'{task95d["profiles"]["seed43_large_256"]["strict_correct_count"]}/{task95d["profiles"]["seed43_large_256"]["row_count"]}',
            "light_strict_proxy": f'{task95d["profiles"]["seed43_light_256"]["strict_correct_count"]}/{task95d["profiles"]["seed43_light_256"]["row_count"]}',
            "large_cap_limited": f'{task95d["profiles"]["seed43_large_256"]["cap_limited_incomplete_count"]}/{task95d["profiles"]["seed43_large_256"]["row_count"]}',
            "light_cap_limited": f'{task95d["profiles"]["seed43_light_256"]["cap_limited_incomplete_count"]}/{task95d["profiles"]["seed43_light_256"]["row_count"]}',
            "large_t_compress_ms": _round(task95d["profiles"]["seed43_large_256"]["avg_t_compress_ms"]),
            "light_t_compress_ms": _round(task95d["profiles"]["seed43_light_256"]["avg_t_compress_ms"]),
            "large_e2e_s": _round(task95d["profiles"]["seed43_large_256"]["avg_e2e_time_s"]),
            "light_e2e_s": _round(task95d["profiles"]["seed43_light_256"]["avg_e2e_time_s"]),
            "large_r_actual": _round(task95d["profiles"]["seed43_large_256"]["avg_R_actual"]),
            "light_r_actual": _round(task95d["profiles"]["seed43_light_256"]["avg_R_actual"]),
            "key_takeaway": "Independent seed43 confirmation held with 0/10 fixture overlap against seed42.",
        },
        {
            "task": "T96",
            "status": "PASS_WITH_CAVEAT",
            "sample": "n=30, seed42",
            "setting": "CC-DFlash-R2 / gsm8k_short / max_new_tokens=256",
            "large_strict_proxy": f'{task96["profiles"]["seed42_large_n30_mnt256"]["strict_correct_count"]}/{task96["profiles"]["seed42_large_n30_mnt256"]["row_count"]}',
            "light_strict_proxy": f'{task96["profiles"]["seed42_light_n30_mnt256"]["strict_correct_count"]}/{task96["profiles"]["seed42_light_n30_mnt256"]["row_count"]}',
            "large_cap_limited": f'{task96["profiles"]["seed42_large_n30_mnt256"]["cap_limited_incomplete_count"]}/{task96["profiles"]["seed42_large_n30_mnt256"]["row_count"]}',
            "light_cap_limited": f'{task96["profiles"]["seed42_light_n30_mnt256"]["cap_limited_incomplete_count"]}/{task96["profiles"]["seed42_light_n30_mnt256"]["row_count"]}',
            "large_t_compress_ms": _round(task96["profiles"]["seed42_large_n30_mnt256"]["avg_t_compress_ms"]),
            "light_t_compress_ms": _round(task96["profiles"]["seed42_light_n30_mnt256"]["avg_t_compress_ms"]),
            "large_e2e_s": _round(task96["profiles"]["seed42_large_n30_mnt256"]["avg_e2e_time_s"]),
            "light_e2e_s": _round(task96["profiles"]["seed42_light_n30_mnt256"]["avg_e2e_time_s"]),
            "large_r_actual": _round(task96["profiles"]["seed42_large_n30_mnt256"]["avg_R_actual"]),
            "light_r_actual": _round(task96["profiles"]["seed42_light_n30_mnt256"]["avg_R_actual"]),
            "key_takeaway": "At n=30, light matched large on calibrated strict proxy and remained lower in t_compress_ms and e2e time.",
        },
    ]
    return rows


def build_claim_boundary() -> dict[str, Any]:
    return {
        "task": "Task97",
        "decision": "PASS",
        "allowed_bounded_claims": [
            "light compressor is integrated through the real CC-DFlash runner",
            "in controlled GSM8K mnt256 comparisons, light matched large on calibrated strict proxy at n=30",
            "light reduced average t_compress_ms versus large in the controlled n=30 mnt256 setup",
            "light reduced average e2e time versus large in the controlled n=30 mnt256 setup",
            "mnt256 reduced cap-limited incompleteness relative to mnt128",
            "light compresses less aggressively than large: R_actual about 2.00 vs 2.67",
        ],
        "blocked_claims": [
            "no final speedup claim",
            "no final quality claim",
            "no deployment or 8GB readiness claim",
            "no QMSum semantic correctness claim",
            "no full benchmark claim",
            "no automatic n100 authorization",
            "no claim that GPU compressor placement is better yet",
        ],
    }


def build_next_step_recommendation() -> dict[str, Any]:
    return {
        "task": "Task97",
        "decision": "PASS",
        "recommended_next_task": "T98_optional_n100_go_no_go_decision",
        "alternate_next_task": "T99_light_compressor_gpu_placement_feasibility",
        "reasoning": [
            "Task96 provided bounded n=30 mnt256 evidence that light matched large on calibrated strict proxy while preserving lower t_compress_ms and e2e time.",
            "The project still only has deterministic proxy evidence, so the next step should be gated planning rather than automatic scale-up.",
            "n100 remains optional and blocked until an explicit go/no-go decision is made.",
            "Any GPU-placement follow-up should stay small and gated before larger runs.",
        ],
        "guardrails": {
            "automatic_n100_authorization": False,
            "automatic_qmsum_run": False,
            "automatic_full_benchmark": False,
            "automatic_gpu_switch_default": False,
        },
    }


def build_roadmap_plan_update() -> dict[str, Any]:
    return {
        "task": "Task97",
        "decision": "PASS",
        "future_plan": [
            {
                "task": "T97",
                "title": "Phase 2 Controlled Evidence Packaging",
                "status": "PASS",
                "summary": "Package T93-T96 controlled evidence, preserve claim boundaries, update future roadmap, and fix the Roadmap status-column UI without running a model or benchmark.",
            },
            {
                "task": "T98",
                "title": "Optional n100 Go/No-Go Decision",
                "status": "PLANNED / GATED",
                "summary": "Decision gate only for whether an n100 run is worth doing; this is not automatic authorization.",
            },
            {
                "task": "T99",
                "title": "Light Compressor GPU Placement Feasibility",
                "status": "PLANNED / GATED",
                "summary": "If controlled CPU-path evidence remains favorable, test whether the validated light compressor benefits from CUDA/GPU placement without causing OOM or hurting target/draft generation. Start with n=3 or n=10 gates, not n=30.",
            },
            {
                "task": "T100",
                "title": "Phase 2 Optimization Summary",
                "status": "PLANNED",
                "summary": "Summarize the quality-speed-compression tradeoff after CPU light evidence and any optional GPU-placement feasibility follow-up.",
            },
            {
                "task": "T101",
                "title": "Final Claim Boundary Audit",
                "status": "PLANNED",
                "summary": "Audit supported versus unsupported claims before final report or demo integration.",
            },
            {
                "task": "T102",
                "title": "Final Report Integration",
                "status": "PLANNED",
                "summary": "Integrate the bounded Phase 2 result into final report and demo materials.",
            },
        ],
    }


def write_outputs(output_dir: Path, summary: dict[str, Any], table_rows: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "task97_phase2_evidence_summary.json", summary)
    _write_json(output_dir / "task97_claim_boundary.json", build_claim_boundary())
    _write_json(output_dir / "task97_next_step_recommendation.json", build_next_step_recommendation())
    _write_json(output_dir / "task97_roadmap_plan_update.json", build_roadmap_plan_update())

    csv_path = output_dir / "task97_phase2_evidence_table.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(table_rows[0].keys()))
        writer.writeheader()
        writer.writerows(table_rows)


def analyze(output_dir: Path, paths: dict[str, Path] | None = None) -> dict[str, Any]:
    data = load_inputs(paths)
    summary = build_evidence_summary(data)
    table_rows = build_evidence_table(data)
    write_outputs(output_dir, summary, table_rows)
    return {
        "summary": summary,
        "claim_boundary": build_claim_boundary(),
        "next_step_recommendation": build_next_step_recommendation(),
        "roadmap_plan_update": build_roadmap_plan_update(),
        "table_rows": table_rows,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Package controlled Phase 2 evidence from Task93 through Task96.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for Task97 packaging artifacts.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    analyze(args.output_dir)
    print(f"wrote_summary={args.output_dir / 'task97_phase2_evidence_summary.json'}")
    print(f"wrote_table={args.output_dir / 'task97_phase2_evidence_table.csv'}")
    print(f"wrote_claim_boundary={args.output_dir / 'task97_claim_boundary.json'}")
    print(f"wrote_next_step={args.output_dir / 'task97_next_step_recommendation.json'}")
    print(f"wrote_roadmap_plan={args.output_dir / 'task97_roadmap_plan_update.json'}")


if __name__ == "__main__":
    main()
