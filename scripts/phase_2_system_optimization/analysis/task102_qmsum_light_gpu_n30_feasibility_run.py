from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any

DEFAULT_BASE_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102_qmsum_light_gpu_n30_feasibility_run"
)
DEFAULT_SMOKE_GLOB = DEFAULT_BASE_DIR / "smoke"
DEFAULT_N30_GLOB = DEFAULT_BASE_DIR / "runs"

OUTPUT_RELATIVE_PATHS = (
    Path("summary/task102_qmsum_feasibility_summary.json"),
    Path("summary/task102_qmsum_run_status.json"),
    Path("summary/task102_next_task_decision.json"),
    Path("summary/task102_phase2_claim_closure_roadmap.json"),
    Path("summary/task102_claim_status_map.json"),
    Path("tables/task102_qmsum_runtime_table.csv"),
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path or not path.exists():
        return rows
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_no} is not a JSON object")
        rows.append(payload)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _latest_jsonl(folder: Path) -> Path | None:
    files = sorted(folder.glob("*.jsonl"))
    return files[-1] if files else None


def _number(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def _unique(rows: list[dict[str, Any]], *keys: str) -> list[Any]:
    seen: list[Any] = []
    for row in rows:
        for key in keys:
            if key not in row:
                continue
            value = row[key]
            if key == "local_files_only":
                bool_value = _boolish(value)
                if bool_value is not None:
                    value = bool_value
            if value not in seen:
                seen.append(value)
    return seen


def _stats(values: list[float]) -> dict[str, float | None]:
    clean = [value for value in values if value is not None]
    if not clean:
        return {"avg": None, "min": None, "max": None, "p95": None}
    ordered = sorted(clean)
    p95_index = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return {
        "avg": round(statistics.fmean(clean), 6),
        "min": round(min(clean), 6),
        "max": round(max(clean), 6),
        "p95": round(ordered[p95_index], 6),
    }


def _generated_text(row: dict[str, Any]) -> str:
    value = row.get("generated_text", "")
    return value if isinstance(value, str) else ""


def _looks_cap_limited(row: dict[str, Any]) -> bool:
    max_new_tokens = _number(row, "max_new_tokens")
    if not max_new_tokens:
        return False
    generated_tokens = _number(row, "generated_token_count", "output_tokens", "new_tokens")
    if generated_tokens is not None and generated_tokens >= max_new_tokens:
        return True
    text = _generated_text(row).strip()
    return bool(text) and not text.endswith((".", "?", "!", '"', "'", ")", "]"))


def _failure_flag(row: dict[str, Any]) -> bool:
    for key, value in row.items():
        lowered = key.lower()
        if "oom" in lowered or "cuda" in lowered or "failure" in lowered or "error" in lowered:
            if lowered in {"cuda_available", "torch_cuda"}:
                continue
            if value in (None, "", False, 0, "False", "false", "none", "None"):
                continue
            return True
    return False


def summarize_artifact(path: Path | None, *, expected_rows: int, run_kind: str) -> dict[str, Any]:
    rows = read_jsonl(path) if path else []
    metric_values = {
        "t_compress_ms": [_number(row, "t_compress_ms") for row in rows],
        "e2e_time_s": [
            _number(row, "e2e_time_s", "e2e_s", "total_time_s", "generation_time_s") for row in rows
        ],
        "tokens_per_second": [_number(row, "tokens_per_second", "tok_per_sec") for row in rows],
        "tau_mean": [_number(row, "tau_mean") for row in rows],
        "t_prefill_ms": [_number(row, "t_prefill_ms") for row in rows],
        "R_actual": [_number(row, "R_actual", "r_actual") for row in rows],
        "vram_allocated_gib": [_number(row, "vram_allocated_gib", "prefill_vram_allocated_gib") for row in rows],
        "vram_reserved_gib": [_number(row, "vram_reserved_gib", "prefill_vram_reserved_gib") for row in rows],
    }
    stats = {name: _stats([value for value in values if value is not None]) for name, values in metric_values.items()}
    empty_count = sum(1 for row in rows if not _generated_text(row).strip())
    cap_limited_count = sum(1 for row in rows if _looks_cap_limited(row))
    failure_count = sum(1 for row in rows if _failure_flag(row))
    metadata = {
        "condition": _unique(rows, "condition"),
        "dataset_name": _unique(rows, "dataset_name", "dataset"),
        "compressor_profile": _unique(rows, "compressor_profile"),
        "compressor_device_map": _unique(rows, "compressor_device_map", "resolved_compressor_device_map"),
        "requested_compressor_device_map": _unique(rows, "requested_compressor_device_map"),
        "local_files_only": _unique(rows, "local_files_only"),
        "max_new_tokens": _unique(rows, "max_new_tokens"),
        "qmsum_answer_policy_type": _unique(rows, "qmsum_answer_policy_type"),
    }
    metadata_confirms_light_gpu = (
        metadata["compressor_profile"] == ["light"]
        and "cuda" in metadata["compressor_device_map"]
        and (not metadata["requested_compressor_device_map"] or "cuda" in metadata["requested_compressor_device_map"])
    )
    return {
        "artifact": str(path) if path else None,
        "run_kind": run_kind,
        "expected_rows": expected_rows,
        "row_count": len(rows),
        "run_complete": len(rows) == expected_rows,
        "empty_or_malformed_output_count": empty_count,
        "cap_limited_or_truncated_heuristic_count": cap_limited_count,
        "oom_cuda_or_failure_flag_count": failure_count,
        "metadata": metadata,
        "metadata_confirms_light_gpu": metadata_confirms_light_gpu,
        "stats": stats,
        "max_vram_reserved_gib": stats["vram_reserved_gib"]["max"],
    }


def build_run_status(smoke_artifact: Path | None, n30_artifact: Path | None) -> dict[str, Any]:
    return {
        "smoke": summarize_artifact(smoke_artifact, expected_rows=3, run_kind="smoke"),
        "n30": summarize_artifact(n30_artifact, expected_rows=30, run_kind="n30"),
    }


def _n30_passed(run_status: dict[str, Any]) -> bool:
    n30 = run_status.get("n30", {})
    return bool(
        n30.get("run_complete")
        and n30.get("metadata_confirms_light_gpu")
        and n30.get("empty_or_malformed_output_count") == 0
        and n30.get("oom_cuda_or_failure_flag_count") == 0
    )


def _smoke_passed(run_status: dict[str, Any]) -> bool:
    smoke = run_status.get("smoke", {})
    return bool(
        smoke.get("run_complete")
        and smoke.get("metadata_confirms_light_gpu")
        and smoke.get("empty_or_malformed_output_count") == 0
        and smoke.get("oom_cuda_or_failure_flag_count") == 0
    )


def build_next_task_decision(run_status: dict[str, Any]) -> dict[str, Any]:
    if _n30_passed(run_status):
        return {
            "next_task": "T102B — QMSum Output + Semantic-Risk / Proxy / Cap / Latency / VRAM Analysis",
            "reason": "QMSum Light GPU feasibility completed at n=30; the next step is static output and risk analysis, not another benchmark.",
            "automatic_extra_benchmark": False,
            "final_report_integration_now": False,
        }
    return {
        "next_task": "T102A — QMSum Failure Audit / Fix",
        "reason": "QMSum Light GPU feasibility did not complete cleanly; audit the failing/malformed path before any larger scope.",
        "automatic_extra_benchmark": False,
        "final_report_integration_now": False,
    }


def build_claim_status_map(run_status: dict[str, Any]) -> dict[str, Any]:
    n30_complete = _n30_passed(run_status)
    return {
        "GSM8K Light GPU": {
            "status": "CLOSED_PASS_WITH_CAVEAT",
            "wording": "Task100B supports bounded GSM8K Light GPU n100 claims only.",
        },
        "QMSum Light GPU": {
            "status": "FEASIBILITY_COMPLETE_PENDING_T102B_ANALYSIS"
            if n30_complete
            else "BLOCKED_PENDING_T102A",
            "wording": "QMSum Light GPU n30 feasibility observed; semantic-risk/proxy analysis remains pending."
            if n30_complete
            else "QMSum Light GPU feasibility is not complete.",
        },
        "Local 8GB-class feasibility": {
            "status": "STRENGTHENED_BY_GSM8K_N100_AND_QMSUM_N30_LOCAL_OBSERVATION"
            if n30_complete
            else "PARTIAL_GSM8K_ONLY_PENDING_QMSUM",
            "wording": "Local feasibility observed; deployment readiness and universal 8GB claims remain blocked.",
        },
        "Benchmark-scoped quality": {
            "status": "PARTIAL_GSM8K_CLOSED_PENDING_QMSUM_PROXY_ANALYSIS",
            "wording": "GSM8K proxy evidence is closed; QMSum proxy/semantic-risk analysis remains pending.",
        },
        "Benchmark-scoped speed / near-DFlash": {
            "status": "PENDING_T103_REFERENCE_ALIGNMENT",
            "wording": "Reference alignment is required before any near-DFlash speed wording.",
        },
        "DFlash-R1 broken claim": {
            "status": "REMOVED",
            "wording": "DFlash-R1 retained as reference condition",
        },
        "Full matrix / full benchmark": {
            "status": "PENDING_T104",
            "wording": "No full benchmark or full matrix claim is available from T102.",
        },
        "GPU optimized default candidate": {
            "status": "PENDING_T105",
            "wording": "GPU placement remains a gated candidate, not the default.",
        },
        "Final Report Integration": {
            "status": "DEFERRED_OUTSIDE_ACTIVE_PHASE2",
            "wording": "Final report integration is deferred until explicitly requested after claim closure.",
            "active_phase2_next_task": False,
        },
    }


def build_phase2_claim_closure_roadmap(run_status: dict[str, Any]) -> dict[str, Any]:
    next_decision = build_next_task_decision(run_status)
    return {
        "active_phase2_focus": "optimization and benchmark-scoped claim closure",
        "final_report_integration": "deferred outside active Phase 2 until explicitly requested",
        "tasks": [
            {
                "task": "T102",
                "title": "QMSum Light GPU n30 Feasibility Run",
                "status": "PASS_WITH_CAVEAT" if _n30_passed(run_status) else "PARTIAL_OR_FAIL",
                "summary": "Small-gated QMSum Light GPU feasibility run; no QMSum n100 or full matrix.",
            },
            {
                "task": "T102A",
                "title": "QMSum Failure Audit / Fix",
                "status": "CONDITIONAL",
                "summary": "Activated only if T102 fails, is malformed, or shows unstable metadata.",
            },
            {
                "task": "T102B",
                "title": "QMSum Output + Semantic-Risk / Proxy / Cap / Latency / VRAM Analysis",
                "status": "PLANNED / NEXT" if _n30_passed(run_status) else "BLOCKED BY T102",
                "summary": "Analyze generated QMSum outputs and risk boundaries without a new benchmark.",
            },
            {
                "task": "T103",
                "title": "Reference Alignment for Speed Claim",
                "status": "PLANNED",
                "summary": "Align speed reference wording before any near-DFlash claim.",
            },
            {
                "task": "T104",
                "title": "Full Matrix / Benchmark-Scope Claim Closure",
                "status": "PLANNED",
                "summary": "Close what is and is not covered by the benchmark scope.",
            },
            {
                "task": "T105",
                "title": "Optimized Default Candidate Decision",
                "status": "PLANNED",
                "summary": "Decide whether GPU placement can become a candidate default; not automatic.",
            },
            {
                "task": "T106",
                "title": "Phase 2 Optimization Closure Pack",
                "status": "PLANNED",
                "summary": "Package Phase 2 optimization evidence after claim closure.",
            },
        ],
        "current_next": next_decision["next_task"],
    }


def _decision(run_status: dict[str, Any]) -> str:
    if _n30_passed(run_status):
        return "PASS_WITH_CAVEAT"
    if _smoke_passed(run_status):
        return "PARTIAL"
    return "FAIL"


def _write_runtime_table(path: Path, run_status: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "run_kind",
        "row_count",
        "run_complete",
        "avg_t_compress_ms",
        "avg_e2e_time_s",
        "avg_tokens_per_second",
        "avg_tau_mean",
        "avg_R_actual",
        "max_vram_reserved_gib",
        "empty_or_malformed_output_count",
        "oom_cuda_or_failure_flag_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for kind in ("smoke", "n30"):
            status = run_status[kind]
            stats = status["stats"]
            writer.writerow(
                {
                    "run_kind": kind,
                    "row_count": status["row_count"],
                    "run_complete": status["run_complete"],
                    "avg_t_compress_ms": stats["t_compress_ms"]["avg"],
                    "avg_e2e_time_s": stats["e2e_time_s"]["avg"],
                    "avg_tokens_per_second": stats["tokens_per_second"]["avg"],
                    "avg_tau_mean": stats["tau_mean"]["avg"],
                    "avg_R_actual": stats["R_actual"]["avg"],
                    "max_vram_reserved_gib": status["max_vram_reserved_gib"],
                    "empty_or_malformed_output_count": status["empty_or_malformed_output_count"],
                    "oom_cuda_or_failure_flag_count": status["oom_cuda_or_failure_flag_count"],
                }
            )


def analyze(
    *,
    smoke_artifact: Path | None,
    n30_artifact: Path | None,
    output_dir: Path = DEFAULT_BASE_DIR,
) -> dict[str, Any]:
    run_status = build_run_status(smoke_artifact=smoke_artifact, n30_artifact=n30_artifact)
    decision = _decision(run_status)
    next_task = build_next_task_decision(run_status)
    claim_status_map = build_claim_status_map(run_status)
    roadmap = build_phase2_claim_closure_roadmap(run_status)
    summary = {
        "task": "T102",
        "decision": decision,
        "dataset": "qmsum_meeting_qa_long",
        "max_new_tokens": 384,
        "max_new_tokens_rationale": "Task102 uses the canonical Phase 2 QMSum mnt384 diagnostic setting from prior QMSum tasks, not the GSM8K mnt256 setting.",
        "scope": {
            "qmsum_n100_run": False,
            "full_matrix_run": False,
            "other_conditions_run": False,
            "keep_rate_tuning": False,
            "default_config_switch": False,
        },
        "run_status": run_status,
        "next_task_decision": next_task,
        "claim_status_map": claim_status_map,
    }
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[0], summary)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[1], run_status)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[2], next_task)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[3], roadmap)
    write_json(output_dir / OUTPUT_RELATIVE_PATHS[4], claim_status_map)
    _write_runtime_table(output_dir / OUTPUT_RELATIVE_PATHS[5], run_status)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Package Task102 QMSum Light GPU n30 feasibility evidence.")
    parser.add_argument("--smoke-artifact", type=Path, default=None, help="Path to the Task102 n=3 smoke JSONL.")
    parser.add_argument("--n30-artifact", type=Path, default=None, help="Path to the Task102 n=30 JSONL.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_BASE_DIR, help="Task102 output directory.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    smoke = args.smoke_artifact or _latest_jsonl(DEFAULT_SMOKE_GLOB)
    n30 = args.n30_artifact or _latest_jsonl(DEFAULT_N30_GLOB)
    result = analyze(smoke_artifact=smoke, n30_artifact=n30, output_dir=args.output_dir)
    print(json.dumps({"decision": result["decision"], "output_dir": str(args.output_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
