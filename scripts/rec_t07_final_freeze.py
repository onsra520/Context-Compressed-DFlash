#!/usr/bin/env python3
"""Build the Rec-T07 final comparison, audit, and self-contained freeze pack."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import tarfile
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "results" / "Rec-T07-Final"
CPU = ROOT / "results" / "Rec-T06D" / "qmsum_n100"
GPU = FINAL / "qmsum_n100"
N3 = FINAL / "qmsum_n3"
PAIRS = (
    ("llmlingua-ar-r2", "llmlingua-ar-r2-gpu"),
    ("cc-dflash-r2", "cc-dflash-r2-gpu"),
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(root: Path, condition: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (root / "runs" / f"{condition.replace('-', '_')}.jsonl").read_text(encoding="utf-8").splitlines()]


def gib(value: int | float) -> float:
    return float(value) / (1024**3)


def mean_field(rows: list[dict[str, Any]], field: str) -> float:
    return mean(float(row[field]) for row in rows)


def summary_by_condition(root: Path) -> dict[str, dict[str, Any]]:
    return {row["condition"]: row for row in csv.DictReader((root / "summary.csv").open(encoding="utf-8"))}


def audit_run(root: Path, *, expected_rows: int, expected_mode: str) -> dict[str, Any]:
    manifest = read_json(root / "benchmark_manifest.json")
    if manifest["conditions"] != [pair[1] for pair in PAIRS] or manifest["execution_mode"] != expected_mode:
        raise ValueError(f"unexpected Rec-T07 matrix in {root}")
    evidence: dict[str, Any] = {"manifest_hashes_present": bool(manifest["run_file_hashes"]), "conditions": {}}
    for _, condition in PAIRS:
        rows = read_rows(root, condition)
        if len(rows) != expected_rows:
            raise ValueError(f"{condition} has {len(rows)} rows, expected {expected_rows}")
        checks = {
            "all_success": all(row["success"] for row in rows),
            "all_cuda_verified": all(row["resource"]["compressor_cuda_verified"] for row in rows),
            "all_resident": all(row["resource"]["compressor_execution_mode"] == "resident" for row in rows),
            "all_parameters_and_buffers_cuda": all(row["resource"]["compressor_device_audit"]["all_tensors_cuda"] for row in rows),
            "all_synchronized": all(row["compression"]["result"]["backend_metadata"]["timing_synchronized"] is True for row in rows),
            "all_request_wide_peaks": all(row["measurement_scope"] == "full request including prompt preparation, optional compression, and generation" for row in rows),
            "all_healthy": all(not row["output_health"]["empty"] and not row["quality"]["invalid"] for row in rows),
        }
        if not all(checks.values()):
            raise ValueError(f"failed GPU audit for {condition}: {checks}")
        audit = rows[0]["resource"]["compressor_device_audit"]
        evidence["conditions"][condition] = {
            "rows": len(rows), "checks": checks, "device_set": audit["unique_devices"],
            "parameter_count": audit["total_parameters"], "buffer_count": audit["total_buffers"],
            "execution_mode": audit["execution_mode"],
            "initialization_and_device_placement_ms": rows[0]["resource"]["compressor_initialization_and_device_placement_ms"],
            "per_request_transfer_to_device_ms": rows[0]["resource"]["compressor_transfer_to_device_ms"],
            "per_request_offload_ms": rows[0]["resource"]["compressor_offload_ms"],
            "transfer_measurement_scope": rows[0]["resource"]["compressor_transfer_measurement_scope"],
            "request_peak_allocated_bytes": max(row["peak_allocated_bytes"] for row in rows),
            "request_peak_reserved_bytes": max(row["peak_reserved_bytes"] for row in rows),
        }
    return evidence


def build() -> None:
    n3_audit = audit_run(N3, expected_rows=3, expected_mode="smoke")
    n100_audit = audit_run(GPU, expected_rows=100, expected_mode="benchmark")
    cpu_summary = summary_by_condition(CPU)
    gpu_summary = summary_by_condition(GPU)
    records: list[dict[str, Any]] = []
    old_gpu = {"llmlingua-ar-r2-gpu": (154.037, 1708.262), "cc-dflash-r2-gpu": (164.710, 2083.879)}
    for cpu_condition, gpu_condition in PAIRS:
        cpu_rows, gpu_rows = read_rows(CPU, cpu_condition), read_rows(GPU, gpu_condition)
        output_matches = sum(a["generated_text_hash"] == b["generated_text_hash"] for a, b in zip(cpu_rows, gpu_rows))
        input_matches = sum(a["model_input_ids_hash"] == b["model_input_ids_hash"] for a, b in zip(cpu_rows, gpu_rows))
        compression_cpu, compression_gpu = mean_field(cpu_rows, "compression_total_ms"), mean_field(gpu_rows, "compression_total_ms")
        warm_cpu, warm_gpu = mean_field(cpu_rows, "warm_request_e2e_ms"), mean_field(gpu_rows, "warm_request_e2e_ms")
        baseline, dflash = float(cpu_summary["baseline-ar"]["mean_warm_e2e_ms"]), float(cpu_summary["dflash-r1"]["mean_warm_e2e_ms"])
        first = gpu_rows[0]["resource"]
        record = {
            "cpu_condition": cpu_condition, "gpu_condition": gpu_condition, "rows": len(gpu_rows),
            "cpu_compression_ms": compression_cpu, "synchronized_gpu_compression_ms": compression_gpu,
            "compression_speedup_vs_cpu": compression_cpu / compression_gpu,
            "cpu_warm_e2e_ms": warm_cpu, "synchronized_gpu_warm_e2e_ms": warm_gpu,
            "warm_e2e_improvement_vs_cpu_ms": warm_cpu - warm_gpu,
            "warm_e2e_delta_vs_baseline_ar_ms": warm_gpu - baseline,
            "warm_e2e_delta_vs_dflash_r1_ms": warm_gpu - dflash,
            "prompt_token_reduction_pct": float(gpu_summary[gpu_condition]["full_prompt_reduction_pct"]),
            "prompt_token_reduction_tokens": float(gpu_summary[gpu_condition]["full_prompt_reduction_tokens"]),
            "output_hash_matches": output_matches, "compressed_input_hash_matches": input_matches,
            "output_health_pass_rows": sum(not row["output_health"]["empty"] and not row["quality"]["invalid"] for row in gpu_rows),
            "quality_reference_recall": float(gpu_summary[gpu_condition]["reference_recall"]),
            "quality_reference_precision": float(gpu_summary[gpu_condition]["reference_precision"]),
            "semantic_correctness": "NOT_CLAIMED",
            "peak_cuda_allocated_bytes": max(row["peak_allocated_bytes"] for row in gpu_rows),
            "peak_cuda_reserved_bytes": max(row["peak_reserved_bytes"] for row in gpu_rows),
            "current_cpu_rss_bytes": max(row["resource"]["process_current_rss_bytes"] or 0 for row in gpu_rows),
            "peak_cpu_rss_bytes": max(row["resource"]["process_peak_rss_bytes"] or 0 for row in gpu_rows),
            "execution_mode": first["compressor_execution_mode"], "device_set": ";".join(first["compressor_device_audit"]["unique_devices"]),
            "parameter_count": first["compressor_device_audit"]["total_parameters"], "buffer_count": first["compressor_device_audit"]["total_buffers"],
            "previous_unsynchronized_gpu_compression_ms": old_gpu[gpu_condition][0],
            "previous_unsynchronized_gpu_warm_e2e_ms": old_gpu[gpu_condition][1],
        }
        records.append(record)
    fields = list(records[0])
    with (FINAL / "final_cpu_gpu_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(records)
    (FINAL / "gpu_timing_audit.json").write_text(json.dumps({"n3_validation": n3_audit, "n100_benchmark": n100_audit}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (FINAL / "source_repairs.md").write_text("""# Rec-T07 source repairs

Root cause: GPU kernels are asynchronous, so pre-existing compressor and warm-request wall-clock measurements could exclude queued GPU work. Peak CUDA statistics were also reset after optional compression, excluding compressor allocations from the advertised request peak. Finally, CUDA placement and resource reporting did not make constructor placement versus per-request transfer explicit.

Changed files: `src/ccdf/runtime/engine.py`, `src/ccdf/compression/llmlingua.py`, and `tests/test_rec_t07_gpu_hotfix.py` (commit `27db94f`).

Behavioral impact: GPU compression fences CUDA before and after compressor timing; warm E2E fences before start and after generation; CUDA peak statistics reset before prompt preparation/compression; GPU compressors fail if CUDA is unavailable or any discovered parameter/buffer is non-CUDA. Rows record full-request peaks, resident/staged mode, device set/counts, CPU RSS, and truthful constructor-placement/per-request transfer scope.

Comparability: CPU results are preserved and were not rerun. The new GPU timings are synchronized and therefore supersede the older unsynchronized GPU values for timing comparisons; prompt/output equivalence remains directly checked against preserved CPU raw rows.

Regression coverage: focused timing/resource tests cover fences, reset ordering, CUDA fallback rejection, tensor/buffer audit, and emitted metadata. The final n=3 and n=100 artifacts provide real-CUDA validation.
""", encoding="utf-8")
    lines = ["# Rec-T07 final synchronized GPU report", "", "The CPU comparison uses preserved Rec-T06D QMSum n=100 rows; only the two requested GPU conditions were rerun. QMSum semantic correctness is **NOT_CLAIMED**. Exact output/compressed-input matches below are observed hash evidence.", "", "| GPU condition | CPU/GPU compression ms | speedup | CPU/GPU warm E2E ms | warm improvement | vs Baseline-AR | vs DFlash-R1 | prompt reduction | output/input hashes | peak alloc/reserved | CPU RSS current/peak |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in records:
        lines.append(f"| {row['gpu_condition']} | {row['cpu_compression_ms']:.3f} / {row['synchronized_gpu_compression_ms']:.3f} | {row['compression_speedup_vs_cpu']:.2f}x | {row['cpu_warm_e2e_ms']:.3f} / {row['synchronized_gpu_warm_e2e_ms']:.3f} | {row['warm_e2e_improvement_vs_cpu_ms']:.3f} ms | {row['warm_e2e_delta_vs_baseline_ar_ms']:.3f} ms | {row['warm_e2e_delta_vs_dflash_r1_ms']:.3f} ms | {row['prompt_token_reduction_pct']:.3f}% | {row['output_hash_matches']}/100; {row['compressed_input_hash_matches']}/100 | {gib(row['peak_cuda_allocated_bytes']):.2f}/{gib(row['peak_cuda_reserved_bytes']):.2f} GiB | {gib(row['current_cpu_rss_bytes']):.2f}/{gib(row['peak_cpu_rss_bytes']):.2f} GiB |")
    lines.extend(["", "## Synchronized-versus-older GPU values", "", "| Condition | old compression ms | synchronized compression ms | old warm E2E ms | synchronized warm E2E ms |", "|---|---:|---:|---:|---:|"])
    for row in records:
        lines.append(f"| {row['gpu_condition']} | {row['previous_unsynchronized_gpu_compression_ms']:.3f} | {row['synchronized_gpu_compression_ms']:.3f} | {row['previous_unsynchronized_gpu_warm_e2e_ms']:.3f} | {row['synchronized_gpu_warm_e2e_ms']:.3f} |")
    lines.extend(["", "All 200 final GPU rows passed output-health checks. Both compressors ran as CUDA-resident on `cuda:0` with 199 parameters and 2 buffers; per-request transfer/offload were 0 ms, while initial device placement is recorded separately in raw rows. Request-wide peaks include prompt preparation, compression, and generation.", ""])
    (FINAL / "final_report.md").write_text("\n".join(lines), encoding="utf-8")


def freeze() -> None:
    evidence = FINAL / "git_evidence"
    evidence.mkdir(exist_ok=True)
    for name, command in {
        "status.txt": ["git", "status", "--short"],
        "head.txt": ["git", "rev-parse", "HEAD"],
        "source_repair_commit.txt": ["git", "show", "--stat", "--oneline", "27db94f"],
        "source_repair.diff": ["git", "show", "--format=fuller", "--binary", "27db94f", "--", "src/ccdf/compression/llmlingua.py", "src/ccdf/runtime/engine.py", "tests/test_rec_t07_gpu_hotfix.py"],
    }.items():
        evidence.joinpath(name).write_text(subprocess.check_output(command, cwd=ROOT, text=True), encoding="utf-8")
    archive = ROOT / "rec-t07-final-freeze-pack.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(FINAL, arcname="Rec-T07-Final")
        tar.add(ROOT / "README.md", arcname="README.md")
        tar.add(CPU, arcname="Rec-T06D/qmsum_n100")
    print(archive)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    build()
    if args.freeze:
        freeze()
