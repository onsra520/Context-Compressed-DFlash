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
    "results/phase_2_system_optimization/compressor_comparison/"
    "task99_light_compressor_gpu_placement_feasibility"
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
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


def _avg(values: list[float | None]) -> float | None:
    numeric = [value for value in values if isinstance(value, (int, float))]
    if not numeric:
        return None
    return round(mean(float(value) for value in numeric), 6)


def _round2(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 2)
    return value


def _failure_flags(rows: list[dict[str, Any]]) -> dict[str, Any]:
    messages = [str(row.get("task99_gpu_failure", "")).strip() for row in rows if row.get("task99_gpu_failure")]
    types = [str(row.get("task99_gpu_failure_type", "")).strip().lower() for row in rows if row.get("task99_gpu_failure_type")]
    oom_or_cuda = any("oom" in value or "cuda" in value for value in types + [msg.lower() for msg in messages])
    shell_gpu_unavailable = any("gpu_unavailable" in value for value in types)
    return {
        "failure_messages": messages,
        "failure_types": types,
        "oom_or_cuda_failure": oom_or_cuda,
        "shell_gpu_unavailable": shell_gpu_unavailable,
    }


def summarize_gpu_artifact(path: Path) -> dict[str, Any]:
    rows = load_jsonl(path)
    flags = _failure_flags(rows)
    if rows and any(row.get("task99_gpu_failure") for row in rows):
        return {
            "artifact": str(path),
            "row_count": len(rows),
            "metadata_ok": False,
            "compressor_profile": rows[0].get("compressor_profile"),
            "compressor_device_map": rows[0].get("compressor_device_map"),
            "requested_compressor_device_map": rows[0].get("requested_compressor_device_map"),
            "failure_flags": flags,
            "strict_correct_count": 0,
            "cap_limited_incomplete_count": 0,
            "final_answer_marker_count": 0,
            "strict_wrong_numeric_count": 0,
            "avg_t_compress_ms": None,
            "avg_R_actual": None,
            "avg_e2e_time_s": None,
            "avg_tokens_per_second": None,
            "avg_tau_mean": None,
            "avg_t_prefill_ms": None,
            "avg_vram_allocated_gib": None,
            "avg_vram_reserved_gib": None,
            "avg_prefill_vram_allocated_gib": None,
            "avg_prefill_vram_reserved_gib": None,
            "calibrated_label_counts": {},
            "labels": [],
        }

    labels = [
        t95b.calibrate_row(row, profile="light_gpu", row_index=index, artifact=path)
        for index, row in enumerate(rows, start=1)
    ]
    metadata_ok = (
        all(row.get("condition") == "CC-DFlash-R2" for row in rows)
        and all(row.get("dataset_name") == "gsm8k_short" for row in rows)
        and all(str(row.get("compressor_profile")) == "light" for row in rows)
        and all(str(row.get("compressor_device_map")) in {"cuda", "cuda:0"} for row in rows)
        and all(row.get("local_files_only") is True for row in rows)
        and all(bool(row.get("compressor_path")) for row in rows)
        and all(bool(row.get("resolved_compressor_path")) for row in rows)
    )
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
    return {
        "artifact": str(path),
        "row_count": len(rows),
        "metadata_ok": metadata_ok,
        "compressor_profile": rows[0].get("compressor_profile") if rows else None,
        "compressor_device_map": rows[0].get("compressor_device_map") if rows else None,
        "requested_compressor_device_map": rows[0].get("requested_compressor_device_map") if rows else None,
        "failure_flags": flags,
        "strict_correct_count": sum(1 for item in labels if item.get("strict_correct")),
        "cap_limited_incomplete_count": label_counts["cap_limited_incomplete"],
        "final_answer_marker_count": sum(1 for item in labels if item.get("final_answer_marker_present")),
        "strict_wrong_numeric_count": label_counts["strict_wrong_numeric"],
        "avg_t_compress_ms": _avg([_numeric(row, "t_compress_ms") for row in rows]),
        "avg_R_actual": _avg([_numeric(row, "R_actual") for row in rows]),
        "avg_e2e_time_s": _avg(
            [
                (_numeric(row, "e2e_time_s") if _numeric(row, "e2e_time_s") is not None else (
                    (_numeric(row, "generation_time_s") or 0.0) + ((_numeric(row, "t_compress_ms") or 0.0) / 1000.0)
                ))
                for row in rows
            ]
        ),
        "avg_tokens_per_second": _avg([_numeric(row, "tokens_per_second", "tok_per_sec") for row in rows]),
        "avg_tau_mean": _avg([_numeric(row, "tau_mean") for row in rows]),
        "avg_t_prefill_ms": _avg([_numeric(row, "t_prefill_ms") for row in rows]),
        "avg_vram_allocated_gib": _avg([_numeric(row, "vram_allocated_gib") for row in rows]),
        "avg_vram_reserved_gib": _avg([_numeric(row, "vram_reserved_gib") for row in rows]),
        "avg_prefill_vram_allocated_gib": _avg([_numeric(row, "prefill_vram_allocated_gib") for row in rows]),
        "avg_prefill_vram_reserved_gib": _avg([_numeric(row, "prefill_vram_reserved_gib") for row in rows]),
        "calibrated_label_counts": label_counts,
        "labels": labels,
    }


def _load_reference(path: Path, *, historical_only: bool = False, note: str | None = None) -> dict[str, Any]:
    payload = load_json(path)
    payload["path"] = str(path)
    payload["historical_only"] = historical_only
    payload["comparison_note"] = note
    return payload


def _comparison_section(gpu_run: dict[str, Any], reference: dict[str, Any], *, label: str) -> dict[str, Any]:
    row_count = reference.get("row_count") or reference.get("n")
    max_new_tokens = reference.get("max_new_tokens")
    strict_correct = reference.get("strict_correct_count")
    cap_limited = reference.get("cap_limited_incomplete_count")
    final_markers = reference.get("final_answer_marker_count")
    strict_wrong = reference.get("strict_wrong_numeric_count")
    blocked_gpu_run = bool(gpu_run.get("failure_flags", {}).get("oom_or_cuda_failure")) or not bool(gpu_run.get("metadata_ok"))
    comparisons = {
        "strict_correct_delta": (
            gpu_run["strict_correct_count"] - strict_correct
            if not blocked_gpu_run and isinstance(strict_correct, int)
            else None
        ),
        "cap_limited_incomplete_delta": (
            gpu_run["cap_limited_incomplete_count"] - cap_limited
            if not blocked_gpu_run and isinstance(cap_limited, int)
            else None
        ),
        "final_answer_marker_delta": (
            gpu_run["final_answer_marker_count"] - final_markers
            if not blocked_gpu_run and isinstance(final_markers, int)
            else None
        ),
        "strict_wrong_numeric_delta": (
            gpu_run["strict_wrong_numeric_count"] - strict_wrong
            if not blocked_gpu_run and isinstance(strict_wrong, int)
            else None
        ),
        "avg_t_compress_ms_delta": (
            round(gpu_run["avg_t_compress_ms"] - reference.get("avg_t_compress_ms"), 6)
            if isinstance(gpu_run["avg_t_compress_ms"], float) and isinstance(reference.get("avg_t_compress_ms"), (int, float))
            else None
        ),
        "avg_e2e_time_s_delta": (
            round(gpu_run["avg_e2e_time_s"] - reference.get("avg_e2e_time_s"), 6)
            if isinstance(gpu_run["avg_e2e_time_s"], float) and isinstance(reference.get("avg_e2e_time_s"), (int, float))
            else None
        ),
        "avg_tokens_per_second_delta": (
            round(gpu_run["avg_tokens_per_second"] - reference.get("avg_tokens_per_second"), 6)
            if isinstance(gpu_run["avg_tokens_per_second"], float) and isinstance(reference.get("avg_tokens_per_second"), (int, float))
            else None
        ),
        "avg_tau_mean_delta": (
            round(gpu_run["avg_tau_mean"] - reference.get("avg_tau_mean"), 6)
            if isinstance(gpu_run["avg_tau_mean"], float) and isinstance(reference.get("avg_tau_mean"), (int, float))
            else None
        ),
        "avg_t_prefill_ms_delta": (
            round(gpu_run["avg_t_prefill_ms"] - reference.get("avg_t_prefill_ms"), 6)
            if isinstance(gpu_run["avg_t_prefill_ms"], float) and isinstance(reference.get("avg_t_prefill_ms"), (int, float))
            else None
        ),
    }
    return {
        "label": label,
        "reference": reference,
        "comparisons": comparisons,
        "settings_match": (
            reference.get("dataset") == "gsm8k_short"
            and reference.get("condition") in {"CC-DFlash-R2", "DFlash-R1"}
            and max_new_tokens == 256
            and row_count == gpu_run["row_count"]
        ),
    }


def build_recommendation(
    *,
    gpu_run: dict[str, Any],
    task96_light: dict[str, Any],
    n10_present: bool,
) -> dict[str, Any]:
    failure = gpu_run["failure_flags"]["oom_or_cuda_failure"] or not gpu_run["metadata_ok"]
    strict_delta = None
    if isinstance(task96_light.get("strict_correct_count"), int):
        strict_delta = gpu_run["strict_correct_count"] - task96_light["strict_correct_count"]
    cap_delta = None
    if isinstance(task96_light.get("cap_limited_incomplete_count"), int):
        cap_delta = gpu_run["cap_limited_incomplete_count"] - task96_light["cap_limited_incomplete_count"]
    compress_delta = None
    if isinstance(gpu_run.get("avg_t_compress_ms"), float) and isinstance(task96_light.get("avg_t_compress_ms"), (int, float)):
        compress_delta = round(gpu_run["avg_t_compress_ms"] - task96_light["avg_t_compress_ms"], 6)
    e2e_delta = None
    if isinstance(gpu_run.get("avg_e2e_time_s"), float) and isinstance(task96_light.get("avg_e2e_time_s"), (int, float)):
        e2e_delta = round(gpu_run["avg_e2e_time_s"] - task96_light["avg_e2e_time_s"], 6)

    if gpu_run["failure_flags"]["shell_gpu_unavailable"]:
        decision = "PARTIAL"
        reason = "GPU is unavailable in the current agent shell, so runtime feasibility was blocked before smoke execution."
    elif failure and gpu_run["row_count"] <= 1:
        decision = "FAIL"
        reason = "Smoke-level GPU placement failed with CUDA/OOM or invalid placement metadata."
    elif failure or not n10_present:
        decision = "PARTIAL"
        reason = "GPU placement evidence is incomplete or blocked; keep the CPU light path as the supported result."
    elif strict_delta is not None and strict_delta < -1:
        decision = "PARTIAL"
        reason = "GPU placement completed but regressed the bounded strict proxy relative to the Task96 light CPU reference."
    elif cap_delta is not None and cap_delta > 1:
        decision = "PARTIAL"
        reason = "GPU placement increased cap-limited incomplete rows beyond the bounded caveat threshold."
    elif compress_delta is not None and e2e_delta is not None and compress_delta < 0.0 and e2e_delta <= 0.25:
        decision = "PASS_WITH_CAVEAT"
        reason = "Smoke and n10 GPU placement completed with CUDA metadata, no OOM, and bounded quality while compression overhead improved."
    else:
        decision = "PARTIAL"
        reason = "GPU placement completed but did not show a clear bounded benefit over the supported CPU light path."

    return {
        "decision": decision,
        "reason": reason,
        "automatic_default_gpu_switch": False,
        "automatic_n100": False,
        "keep_cpu_light_supported_path": decision != "PASS_WITH_CAVEAT",
        "next_step": (
            "T100_phase2_optimization_summary"
            if decision == "PASS_WITH_CAVEAT"
            else "keep_cpu_light_and_document_gpu_as_experimental"
        ),
    }


def analyze(
    *,
    gpu_artifact: Path,
    output_dir: Path,
    task96_light_reference: Path,
    task96_large_reference: Path,
    dflash_reference: Path | None = None,
) -> dict[str, Any]:
    gpu_run = summarize_gpu_artifact(gpu_artifact)
    task96_light = _load_reference(
        task96_light_reference,
        historical_only=False,
        note="Controlled Task96 light CPU reference; sample size may differ from Task99 smoke/n10.",
    )
    task96_large = _load_reference(
        task96_large_reference,
        historical_only=False,
        note="Controlled Task96 large CPU reference; used only as a bounded CPU-path comparator.",
    )
    dflash = (
        _load_reference(
            dflash_reference,
            historical_only=True,
            note="Historical-only DFlash-R1 reference because Task88 uses a different max_new_tokens policy (512) and Phase 1 benchmark framing.",
        )
        if dflash_reference is not None
        else None
    )

    comparisons = {
        "light_gpu_vs_task96_light_cpu": _comparison_section(gpu_run, task96_light, label="Task96 light CPU"),
        "light_gpu_vs_task96_large_cpu": _comparison_section(gpu_run, task96_large, label="Task96 large CPU"),
    }
    if dflash is not None:
        comparisons["light_gpu_vs_dflash_r1_historical"] = _comparison_section(
            gpu_run,
            dflash,
            label="Task88 DFlash-R1 historical",
        )

    n10_present = gpu_run["row_count"] >= 10 and not gpu_run["failure_flags"]["oom_or_cuda_failure"]
    recommendation = build_recommendation(gpu_run=gpu_run, task96_light=task96_light, n10_present=n10_present)
    decision = recommendation["decision"]

    summary = {
        "task": "Task99",
        "decision": decision,
        "gpu_run": gpu_run,
        "references": {
            "task96_light_cpu": task96_light,
            "task96_large_cpu": task96_large,
            "dflash_historical": dflash,
        },
        "comparisons": comparisons,
        "recommendation": recommendation,
    }

    summary_dir = output_dir / "summary"
    tables_dir = output_dir / "tables"
    summary_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    _write_json(summary_dir / "task99_gpu_placement_summary.json", summary)
    _write_json(summary_dir / "task99_reference_comparison.json", comparisons)
    _write_json(summary_dir / "task99_recommendation.json", recommendation)

    table_rows = [
        {"section": "gpu_run", "label": "row_count", "value": gpu_run["row_count"], "note": ""},
        {"section": "gpu_run", "label": "compressor_device_map", "value": gpu_run["compressor_device_map"], "note": ""},
        {"section": "gpu_run", "label": "strict_correct_count", "value": gpu_run["strict_correct_count"], "note": ""},
        {"section": "gpu_run", "label": "cap_limited_incomplete_count", "value": gpu_run["cap_limited_incomplete_count"], "note": ""},
        {"section": "gpu_run", "label": "avg_t_compress_ms", "value": _round2(gpu_run["avg_t_compress_ms"]), "note": ""},
        {"section": "gpu_run", "label": "avg_e2e_time_s", "value": _round2(gpu_run["avg_e2e_time_s"]), "note": ""},
        {"section": "reference", "label": "task96_light_cpu_avg_t_compress_ms", "value": _round2(task96_light.get("avg_t_compress_ms")), "note": "controlled cpu reference"},
        {"section": "reference", "label": "task96_large_cpu_avg_t_compress_ms", "value": _round2(task96_large.get("avg_t_compress_ms")), "note": "controlled cpu reference"},
        {
            "section": "reference",
            "label": "dflash_r1_avg_e2e_time_s",
            "value": _round2(dflash.get("avg_e2e_time_s")) if dflash else None,
            "note": "historical-only" if dflash else "",
        },
    ]
    _write_csv(tables_dir / "task99_gpu_placement_table.csv", table_rows)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze Task99 light compressor GPU placement feasibility artifacts.")
    parser.add_argument("--gpu-artifact", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--task96-light-reference", type=Path, required=True)
    parser.add_argument("--task96-large-reference", type=Path, required=True)
    parser.add_argument("--dflash-reference", type=Path, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    analyze(
        gpu_artifact=args.gpu_artifact,
        output_dir=args.output_dir,
        task96_light_reference=args.task96_light_reference,
        task96_large_reference=args.task96_large_reference,
        dflash_reference=args.dflash_reference,
    )


if __name__ == "__main__":
    main()
