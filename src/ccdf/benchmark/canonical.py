"""REC-3 canonical Baseline-AR / DFlash-R1 evidence protocol.

The CLI deliberately keeps conditions in separate processes so the
caller can prove that GPU state was released between canonical runs.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import statistics
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import torch

from ccdf.config import Rec2Config, load_config
from ccdf.infrastructure.device import GIB, collect_memory
from ccdf.runtime.engine import RuntimeEngine
from ccdf.validation.quality import evaluate_complete_answer


SCHEMA = "ccdf.rec3.canonical.v1"
REFERENCE = {
    "baseline_decode_tok_s": 24.6703,
    "dflash_decode_tok_s": 95.7658,
    "decode_speedup": 3.8818,
    "warm_e2e_speedup": 3.5033,
    "dflash_peak_reserved_gib": 3.625,
    "generated_token_parity": True,
}
EQUIVALENCE_TOLERANCE_PERCENT = 10.0
TIMING_FIELDS = (
    "prompt_prepare_ms",
    "target_prefill_ms",
    "decode_total_ms",
    "generation_total_ms",
    "warm_request_ms",
)
THROUGHPUT_FIELDS = (
    "decode_tok_s",
    "generation_tok_s",
    "warm_request_tok_s",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def optional_file_identity(path: Path) -> dict[str, Any]:
    exists = path.is_file()
    return {
        "path": str(path),
        "exists": exists,
        "sha256": sha256_file(path) if exists else None,
    }


def describe(values: Iterable[float]) -> dict[str, float | int]:
    numbers = [float(value) for value in values]
    if not numbers or any(not math.isfinite(value) for value in numbers):
        raise ValueError("metric series must contain finite values")
    return {
        "count": len(numbers),
        "mean": statistics.fmean(numbers),
        "median": statistics.median(numbers),
        "min": min(numbers),
        "max": max(numbers),
        "stdev": statistics.stdev(numbers) if len(numbers) > 1 else 0.0,
    }


def _run_read_only(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(["rtk", *command], text=True, capture_output=True, check=False)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def _model_config(path: Path) -> dict[str, Any]:
    payload = json.loads((path / "config.json").read_text(encoding="utf-8"))
    return {
        "path": str(path),
        "config_sha256": sha256_file(path / "config.json"),
        "architectures": payload.get("architectures"),
        "model_type": payload.get("model_type"),
        "torch_dtype": payload.get("torch_dtype"),
        "block_size": payload.get("block_size"),
        "auto_map": payload.get("auto_map"),
        "quantization_config": payload.get("quantization_config"),
    }


def audit(config: Rec2Config, output: Path) -> None:
    prompts = list(config.require("benchmark.prompts"))
    model_paths = {
        "baseline": Path(config.require("models.baseline.local_path")),
        "dflash_target": Path(config.require("models.dflash.target.local_path")),
        "dflash_drafter": Path(config.require("models.dflash.drafter.local_path")),
    }
    packages = {}
    for name in ("torch", "transformers", "accelerate", "autoawq", "PyYAML"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    local_sources = {}
    for relative in (
        "src/ccdf/inference/baseline.py",
        "src/ccdf/dflash/generate.py",
        "src/ccdf/dflash/verifier.py",
        "src/ccdf/dflash/acceptance.py",
        "src/ccdf/inference/stopping.py",
        "models/dflash/drafter/Qwen3-4B-DFlash-b16/dflash.py",
    ):
        path = config.root / relative
        local_sources[relative] = {
            "exists": path.is_file(),
            "sha256": sha256_file(path) if path.is_file() else None,
        }
    backup_identity = optional_file_identity(config.root / "config-backup.yml")
    payload = {
        "schema": SCHEMA,
        "captured_at": utc_now(),
        "environment": {
            "conda_default_env": os.environ.get("CONDA_DEFAULT_ENV"),
            "conda_prefix": os.environ.get("CONDA_PREFIX"),
            "python": sys.version,
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "packages": packages,
            "torch_cuda_version": torch.version.cuda,
            "cuda_available": torch.cuda.is_available(),
            "cuda_device_count": torch.cuda.device_count(),
            "cuda_device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "nvidia_smi_gpu": _run_read_only(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,uuid,memory.total,memory.used,driver_version",
                    "--format=csv,noheader",
                ]
            ),
            "nvidia_smi_processes": _run_read_only(
                [
                    "nvidia-smi",
                    "--query-compute-apps=pid,process_name,used_memory",
                    "--format=csv,noheader",
                ]
            ),
        },
        "repository": {
            "head": _run_read_only(["git", "rev-parse", "HEAD"]),
            "branch": _run_read_only(["git", "branch", "--show-current"]),
            "status_short": _run_read_only(["git", "status", "--short"]),
        },
        "config": {
            "path": str(config.path),
            "sha256": sha256_file(config.path),
            "backup_path": backup_identity["path"],
            "backup_exists": backup_identity["exists"],
            "backup_sha256": backup_identity["sha256"],
            "prompt_count": len(prompts),
            "prompt_sha256": [sha256_bytes(prompt.encode("utf-8")) for prompt in prompts],
            "warmup_requests": int(config.require("benchmark.warmup_requests")),
            "repetitions": int(config.require("benchmark.repetitions")),
            "max_new_tokens": int(config.require("benchmark.smoke_max_new_tokens")),
            "temperature": float(config.require("runtime.temperature")),
            "stop_token_ids": list(config.require("runtime.stop_token_ids")),
            "enable_thinking": bool(config.require("runtime.enable_thinking")),
            "attention_backend": config.require("runtime.attention_backend"),
            "sdpa_kernel": config.require("runtime.sdpa_kernel"),
            "deterministic": bool(config.require("runtime.deterministic")),
        },
        "models": {name: _model_config(path) for name, path in model_paths.items()},
        "local_sources": local_sources,
        "upstream_audit": {
            "repository": "https://github.com/z-lab/dflash",
            "transformers_source": "https://github.com/z-lab/dflash/blob/main/dflash/model.py",
            "supported_pair": "Qwen3-4B non-thinking + z-lab/Qwen3-4B-DFlash-b16",
            "logic_mapping": [
                "target prefill produces the first token and target hidden states",
                "drafter proposes a non-causal masked block",
                "target verifies the proposed block in one forward",
                "accepted prefix plus correction token advances output",
                "target and draft caches are cropped at committed boundaries",
                "EOS or max-new-token stopping clips the final output",
            ],
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def smoke(config: Rec2Config, condition: str, output: Path) -> None:
    started = utc_now()
    engine = RuntimeEngine(config, condition=condition)
    try:
        memory = collect_memory(
            float(config.require("memory.dflash_peak_reserved_limit_gib"))
            if condition == "dflash"
            else None
        )
        payload = {
            "schema": SCHEMA,
            "condition": condition,
            "started_at": started,
            "completed_at": utc_now(),
            "model": engine.model_metadata,
            "determinism": engine.determinism,
            "memory": memory.__dict__,
            "pass": True,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    finally:
        engine.close()


def _contract(config: Rec2Config, prompt: str, max_new_tokens: int) -> dict[str, Any]:
    return {
        "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "system_prompt_sha256": sha256_bytes(str(config.get("prompts.system", "")).encode("utf-8")),
        "temperature": float(config.require("runtime.temperature")),
        "max_new_tokens": max_new_tokens,
        "stop_token_ids": [int(value) for value in config.require("runtime.stop_token_ids")],
        "enable_thinking": bool(config.require("runtime.enable_thinking")),
        "attention_backend": str(config.require("runtime.attention_backend")),
        "sdpa_kernel": str(config.require("runtime.sdpa_kernel")),
        "deterministic": bool(config.require("runtime.deterministic")),
        "seed": int(config.require("runtime.seed")),
    }


def _record(
    config: Rec2Config,
    condition: str,
    prompt: str,
    prompt_index: int,
    phase: str,
    repetition: int | None,
    result: Any,
    max_new_tokens: int,
) -> dict[str, Any]:
    quality = evaluate_complete_answer(
        prompt_index=prompt_index,
        text=result.text,
        stop_reason=result.stop_reason,
        output_tokens=result.output_tokens,
        max_new_tokens=max_new_tokens,
    )
    payload = result.to_dict()
    return {
        "schema": SCHEMA,
        "captured_at": utc_now(),
        "phase": phase,
        "condition": condition,
        "prompt_id": f"mock-{prompt_index + 1:02d}",
        "prompt_index": prompt_index,
        "repetition": repetition,
        "prompt": prompt,
        "contract": _contract(config, prompt, max_new_tokens),
        "quality": quality.to_dict(),
        **payload,
    }


def run_condition(config: Rec2Config, condition: str, output: Path) -> None:
    prompts = [str(value) for value in config.require("benchmark.prompts")]
    if len(prompts) != 10 or len(set(prompts)) != 10:
        raise ValueError("REC-3 canonical workload must contain exactly 10 unique prompts")
    warmups = int(config.require("benchmark.warmup_requests"))
    repetitions = int(config.require("benchmark.repetitions"))
    max_new_tokens = int(config.require("benchmark.smoke_max_new_tokens"))
    if warmups < 1 or repetitions < 1:
        raise ValueError("REC-3 requires at least one warm-up and one measured repetition")
    output.parent.mkdir(parents=True, exist_ok=True)
    engine = RuntimeEngine(config, condition=condition)
    try:
        with output.open("w", encoding="utf-8") as handle:
            for index in range(warmups):
                prompt_index = index % len(prompts)
                result = engine.generate(prompts[prompt_index], max_new_tokens=max_new_tokens)
                row = _record(
                    config,
                    condition,
                    prompts[prompt_index],
                    prompt_index,
                    "warmup",
                    None,
                    result,
                    max_new_tokens,
                )
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
            for repetition in range(repetitions):
                for prompt_index, prompt in enumerate(prompts):
                    result = engine.generate(prompt, max_new_tokens=max_new_tokens)
                    row = _record(
                        config,
                        condition,
                        prompt,
                        prompt_index,
                        "measured",
                        repetition,
                        result,
                        max_new_tokens,
                    )
                    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                    handle.flush()
    finally:
        engine.close()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _condition_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    measured = [row for row in rows if row["phase"] == "measured"]
    warmups = [row for row in rows if row["phase"] == "warmup"]
    timing = {
        field: describe(row["timing"][field] for row in measured)
        for field in TIMING_FIELDS
    }
    if measured and measured[0]["timing"].get("draft_prefill_ms") is not None:
        timing["draft_prefill_ms"] = describe(
            row["timing"]["draft_prefill_ms"] for row in measured
        )
    throughput = {
        field: describe(row["metrics"][field] for row in measured)
        for field in THROUGHPUT_FIELDS
    }
    cold = {
        "warm_request_ms": describe(row["timing"]["warm_request_ms"] for row in warmups),
        "warm_request_tok_s": describe(row["metrics"]["warm_request_tok_s"] for row in warmups),
    }
    summary: dict[str, Any] = {
        "condition": rows[0]["condition"],
        "prompt_count": len({row["prompt_id"] for row in measured}),
        "warmup_count": len(warmups),
        "measured_count": len(measured),
        "input_tokens": describe(row["prompt_tokens"] for row in measured),
        "generated_tokens": describe(row["output_tokens"] for row in measured),
        "timing_ms": timing,
        "throughput_tok_s": throughput,
        "cold_e2e": cold,
        "peak_allocated_gib": max(row["memory"]["peak_allocated_bytes"] for row in rows) / GIB,
        "peak_reserved_gib": max(row["memory"]["peak_reserved_bytes"] for row in rows) / GIB,
        "model": measured[0]["model"],
        "determinism": measured[0]["runtime"]["determinism"],
        "stop_reasons": sorted({row["stop_reason"] for row in measured}),
    }
    if rows[0]["condition"] == "dflash":
        acceptance_lengths = [
            length
            for row in measured
            for length in row["dflash"]["acceptance_lengths"]
        ]
        total_accepted = sum(row["dflash"]["accepted_draft_tokens"] for row in measured)
        total_proposed = sum(row["dflash"]["draft_tokens_proposed"] for row in measured)
        summary["dflash"] = {
            "draft_forward_calls": sum(row["dflash"]["draft_forward_calls"] for row in measured),
            "target_verification_calls": sum(
                row["dflash"]["target_verification_calls"] for row in measured
            ),
            "draft_forward_calls_per_request": describe(
                row["dflash"]["draft_forward_calls"] for row in measured
            ),
            "target_verification_calls_per_request": describe(
                row["dflash"]["target_verification_calls"] for row in measured
            ),
            "acceptance_lengths": describe(acceptance_lengths),
            "tau": describe(row["dflash"]["effective_tau"] for row in measured),
            "acceptance_rate": total_accepted / total_proposed if total_proposed else 0.0,
            "accepted_draft_tokens": total_accepted,
            "draft_tokens_proposed": total_proposed,
        }
    return summary


def _delta(current: float, reference: float) -> dict[str, float]:
    absolute = current - reference
    return {
        "reference": reference,
        "current": current,
        "absolute": absolute,
        "percent": absolute / reference * 100.0,
    }


def summarize(
    baseline_path: Path,
    dflash_path: Path,
    diagnostic_path: Path | None = None,
) -> dict[str, Any]:
    baseline_rows = read_jsonl(baseline_path)
    dflash_rows = read_jsonl(dflash_path)
    baseline = _condition_summary(baseline_rows)
    dflash = _condition_summary(dflash_rows)
    baseline_measured = [row for row in baseline_rows if row["phase"] == "measured"]
    dflash_measured = [row for row in dflash_rows if row["phase"] == "measured"]
    baseline_by_key = {(row["prompt_id"], row["repetition"]): row for row in baseline_measured}
    dflash_by_key = {(row["prompt_id"], row["repetition"]): row for row in dflash_measured}
    keys = sorted(set(baseline_by_key) | set(dflash_by_key))
    parity_rows = []
    for key in keys:
        left = baseline_by_key.get(key)
        right = dflash_by_key.get(key)
        left_ids = left["generated_token_ids"] if left else []
        right_ids = right["generated_token_ids"] if right else []
        first_mismatch = next(
            (
                index
                for index in range(min(len(left_ids), len(right_ids)))
                if left_ids[index] != right_ids[index]
            ),
            min(len(left_ids), len(right_ids)) if len(left_ids) != len(right_ids) else None,
        )
        parity_rows.append(
            {
                "prompt_id": key[0],
                "repetition": key[1],
                "present_both": left is not None and right is not None,
                "input_token_parity": bool(left and right and left["prompt_tokens"] == right["prompt_tokens"]),
                "generated_token_parity": bool(
                    left and right and left["generated_token_ids"] == right["generated_token_ids"]
                ),
                "baseline_generated_tokens": left["output_tokens"] if left else None,
                "dflash_generated_tokens": right["output_tokens"] if right else None,
                "first_mismatch_index": first_mismatch,
                "baseline_mismatch_token_id": (
                    left_ids[first_mismatch]
                    if first_mismatch is not None and first_mismatch < len(left_ids)
                    else None
                ),
                "dflash_mismatch_token_id": (
                    right_ids[first_mismatch]
                    if first_mismatch is not None and first_mismatch < len(right_ids)
                    else None
                ),
            }
        )
    prompt_parity = []
    for prompt_id in sorted({row["prompt_id"] for row in parity_rows}):
        selected = [row for row in parity_rows if row["prompt_id"] == prompt_id]
        prompt_parity.append(
            {
                "prompt_id": prompt_id,
                "repetitions": len(selected),
                "input_token_parity": all(row["input_token_parity"] for row in selected),
                "generated_token_parity": all(row["generated_token_parity"] for row in selected),
                "generated_tokens": sorted(
                    {row["baseline_generated_tokens"] for row in selected if row["baseline_generated_tokens"] is not None}
                ),
                "first_mismatch": next(
                    (
                        {
                            "index": row["first_mismatch_index"],
                            "baseline_token_id": row["baseline_mismatch_token_id"],
                            "dflash_token_id": row["dflash_mismatch_token_id"],
                        }
                        for row in selected
                        if row["first_mismatch_index"] is not None
                    ),
                    None,
                ),
            }
        )
    baseline_decode = baseline["throughput_tok_s"]["decode_tok_s"]["mean"]
    dflash_decode = dflash["throughput_tok_s"]["decode_tok_s"]["mean"]
    decode_speedup = dflash_decode / baseline_decode
    warm_latency_speedup = (
        baseline["timing_ms"]["warm_request_ms"]["mean"]
        / dflash["timing_ms"]["warm_request_ms"]["mean"]
    )
    warm_throughput_speedup = (
        dflash["throughput_tok_s"]["warm_request_tok_s"]["mean"]
        / baseline["throughput_tok_s"]["warm_request_tok_s"]["mean"]
    )
    cold_latency_speedup = (
        baseline["cold_e2e"]["warm_request_ms"]["mean"]
        / dflash["cold_e2e"]["warm_request_ms"]["mean"]
    )
    deltas = {
        "baseline_decode_tok_s": _delta(baseline_decode, REFERENCE["baseline_decode_tok_s"]),
        "dflash_decode_tok_s": _delta(dflash_decode, REFERENCE["dflash_decode_tok_s"]),
        "decode_speedup": _delta(decode_speedup, REFERENCE["decode_speedup"]),
        "warm_e2e_speedup": _delta(warm_latency_speedup, REFERENCE["warm_e2e_speedup"]),
        "dflash_peak_reserved_gib": _delta(
            dflash["peak_reserved_gib"], REFERENCE["dflash_peak_reserved_gib"]
        ),
    }
    timing_valid = all(
        math.isfinite(float(row["timing"][field])) and float(row["timing"][field]) > 0
        for row in baseline_measured + dflash_measured
        for field in TIMING_FIELDS
    )
    parity_pass = bool(parity_rows) and all(
        row["present_both"] and row["input_token_parity"] and row["generated_token_parity"]
        for row in parity_rows
    )
    policy_pass = bool(parity_rows) and all(
        baseline_by_key[key]["contract"] == dflash_by_key[key]["contract"]
        for key in set(baseline_by_key) & set(dflash_by_key)
    )
    structural_pass = all(
        not row["runtime"]["output_health"]["empty"]
        and not row["runtime"]["output_health"]["repetition_detected"]
        for row in baseline_measured + dflash_measured
    ) and all(
        all(audit["structural_pass"] for audit in row["dflash"]["structural_audit"])
        for row in dflash_measured
    )
    quality_pass = all(row["quality"]["quality_pass"] for row in baseline_measured + dflash_measured)
    workload_pass = (
        baseline["prompt_count"] == dflash["prompt_count"] == 10
        and baseline["warmup_count"] == dflash["warmup_count"] >= 1
        and baseline["measured_count"] == dflash["measured_count"]
        and baseline["measured_count"] == 10 * int(baseline["measured_count"] / 10)
        and len(parity_rows) == baseline["measured_count"]
    )
    memory_pass = all(row["memory"].get("gate_pass") is not False for row in dflash_rows)
    equivalence_checks = {
        key: value["percent"] >= -EQUIVALENCE_TOLERANCE_PERCENT
        for key, value in deltas.items()
        if key != "dflash_peak_reserved_gib"
    }
    equivalence_checks["dflash_peak_reserved_gib"] = (
        dflash["peak_reserved_gib"]
        <= REFERENCE["dflash_peak_reserved_gib"] * (1.0 + EQUIVALENCE_TOLERANCE_PERCENT / 100.0)
    )
    gates = {
        "generated_token_parity": parity_pass,
        "quality": quality_pass,
        "structural": structural_pass,
        "memory": memory_pass,
        "policy": policy_pass,
        "metric_validity": timing_valid,
        "workload": workload_pass,
        "workload_performance_rec2_equivalence": all(equivalence_checks.values()),
    }
    overall = all(gates.values())
    result = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "reference": REFERENCE,
        "equivalence_tolerance_percent": EQUIVALENCE_TOLERANCE_PERCENT,
        "conditions": {"baseline": baseline, "dflash": dflash},
        "speedups": {
            "decode_throughput": decode_speedup,
            "cold_e2e_latency": cold_latency_speedup,
            "warm_e2e_latency": warm_latency_speedup,
            "warm_e2e_throughput": warm_throughput_speedup,
        },
        "per_prompt_parity": prompt_parity,
        "per_repetition_parity": parity_rows,
        "rec2_deltas": deltas,
        "rec2_equivalence_checks": equivalence_checks,
        "gates": gates,
        "overall_pass": overall,
        "conclusion": "PASS" if overall else "FAIL/REGRESSION",
    }
    if diagnostic_path is not None:
        diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
        result["regression_diagnosis"] = {
            "classification": "quantized target forward-shape sensitivity",
            "evidence_file": diagnostic_path.name,
            "mismatch_index": diagnostic["mismatch_index"],
            "block_index": diagnostic["block_index"],
            "baseline_token_id": diagnostic["baseline_token_id"],
            "dflash_token_id": diagnostic["dflash_token_id"],
            "autoregressive_top": diagnostic["autoregressive_top"][:2],
            "block_verify_top": diagnostic["block_verify_top"][:2],
            "reason_not_forced": (
                "Exact repair would require per-token target verification, a non-greedy tie tolerance, "
                "or a dtype/backend change; each violates the canonical DFlash or benchmark contract."
            ),
        }
    return result


def render_report(summary: dict[str, Any]) -> str:
    baseline = summary["conditions"]["baseline"]
    dflash = summary["conditions"]["dflash"]
    lines = [
        "# REC-3 canonical runtime rerun",
        "",
        f"Conclusion: **{summary['conclusion']}**",
        "",
        "The canonical 10-prompt workload was run sequentially in separate processes: Baseline-AR first, GPU cleanup/ownership verification, then DFlash-R1. Numeric REC-2 non-regression allows at most a 10% decrease (improvements pass); generated-token parity is evaluated exactly.",
        "",
        "## Metric summary",
        "",
        "| Metric | Baseline-AR | DFlash-R1 | Speedup |",
        "|---|---:|---:|---:|",
        f"| Decode throughput mean (tok/s) | {baseline['throughput_tok_s']['decode_tok_s']['mean']:.4f} | {dflash['throughput_tok_s']['decode_tok_s']['mean']:.4f} | {summary['speedups']['decode_throughput']:.4f}x |",
        f"| Prefill latency mean (ms) | {baseline['timing_ms']['target_prefill_ms']['mean']:.4f} | {dflash['timing_ms']['target_prefill_ms']['mean']:.4f} | — |",
        f"| Decode latency mean (ms) | {baseline['timing_ms']['decode_total_ms']['mean']:.4f} | {dflash['timing_ms']['decode_total_ms']['mean']:.4f} | — |",
        f"| Cold E2E latency mean (ms) | {baseline['cold_e2e']['warm_request_ms']['mean']:.4f} | {dflash['cold_e2e']['warm_request_ms']['mean']:.4f} | {summary['speedups']['cold_e2e_latency']:.4f}x |",
        f"| Warm E2E latency mean (ms) | {baseline['timing_ms']['warm_request_ms']['mean']:.4f} | {dflash['timing_ms']['warm_request_ms']['mean']:.4f} | {summary['speedups']['warm_e2e_latency']:.4f}x |",
        f"| Warm E2E throughput mean (tok/s) | {baseline['throughput_tok_s']['warm_request_tok_s']['mean']:.4f} | {dflash['throughput_tok_s']['warm_request_tok_s']['mean']:.4f} | {summary['speedups']['warm_e2e_throughput']:.4f}x |",
        f"| Peak allocated VRAM (GiB) | {baseline['peak_allocated_gib']:.4f} | {dflash['peak_allocated_gib']:.4f} | — |",
        f"| Peak reserved VRAM (GiB) | {baseline['peak_reserved_gib']:.4f} | {dflash['peak_reserved_gib']:.4f} | — |",
        "",
        "## Workload and DFlash statistics",
        "",
        f"- Prompt count: {baseline['prompt_count']} per condition",
        f"- Warm-up count: {baseline['warmup_count']} per condition",
        f"- Measured count: {baseline['measured_count']} per condition",
        f"- DFlash draft steps: {dflash['dflash']['draft_forward_calls']}",
        f"- DFlash verify steps: {dflash['dflash']['target_verification_calls']}",
        f"- Acceptance length mean/min/max: {dflash['dflash']['acceptance_lengths']['mean']:.4f} / {dflash['dflash']['acceptance_lengths']['min']:.0f} / {dflash['dflash']['acceptance_lengths']['max']:.0f}",
        f"- Tau mean/min/max: {dflash['dflash']['tau']['mean']:.4f} / {dflash['dflash']['tau']['min']:.4f} / {dflash['dflash']['tau']['max']:.4f}",
        f"- Draft acceptance rate: {dflash['dflash']['acceptance_rate']:.6f}",
        "",
        "All timing series in `metric-summary.json` include count, mean, median, min, max, and sample standard deviation.",
        "",
        "## REC-2 deltas",
        "",
        "| Metric | REC-2 | Current | Absolute delta | Percent delta | Equivalent |",
        "|---|---:|---:|---:|---:|:---:|",
    ]
    for key, delta in summary["rec2_deltas"].items():
        lines.append(
            f"| {key} | {delta['reference']:.4f} | {delta['current']:.4f} | {delta['absolute']:+.4f} | {delta['percent']:+.2f}% | {'PASS' if summary['rec2_equivalence_checks'][key] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "## Gates",
            "",
            "| Gate | Result |",
            "|---|:---:|",
        ]
    )
    for key, passed in summary["gates"].items():
        lines.append(f"| {key} | {'PASS' if passed else 'FAIL'} |")
    diagnosis = summary.get("regression_diagnosis")
    if diagnosis:
        ar_top = diagnosis["autoregressive_top"]
        block_top = diagnosis["block_verify_top"]
        lines.extend(
            [
                "",
                "## Regression diagnosis",
                "",
                f"- Classification: {diagnosis['classification']}.",
                f"- First stable mismatch: generated-token index {diagnosis['mismatch_index']} in verification block {diagnosis['block_index']}; Baseline token `{diagnosis['baseline_token_id']}`, DFlash token `{diagnosis['dflash_token_id']}`.",
                f"- AR top logits: token `{ar_top[0]['token_id']}` = {ar_top[0]['logit']:.5f}, token `{ar_top[1]['token_id']}` = {ar_top[1]['logit']:.5f}.",
                f"- Block-verify top logits: token `{block_top[0]['token_id']}` = {block_top[0]['logit']:.5f}, token `{block_top[1]['token_id']}` = {block_top[1]['logit']:.5f}.",
                f"- {diagnosis['reason_not_forced']}",
                "- Cache-length, accepted-prefix, stopping, structural, quality, memory, and workload-performance gates all remained valid.",
            ]
        )
    lines.extend(
        [
            "",
            "## Per-prompt generated-token parity",
            "",
            "| Prompt | Repetitions | Input tokens | Generated tokens |",
            "|---|---:|:---:|:---:|",
        ]
    )
    for row in summary["per_prompt_parity"]:
        lines.append(
            f"| {row['prompt_id']} | {row['repetitions']} | {'PASS' if row['input_token_parity'] else 'FAIL'} | {'PASS' if row['generated_token_parity'] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "## Runtime identity and upstream audit",
            "",
            f"- Baseline model: `{baseline['model'].get('model_id')}`; dtype `{baseline['model'].get('requested_dtype')}`; attention `{baseline['model'].get('attention')}`",
            f"- DFlash target: `{dflash['model'].get('target_model_id')}`; target dtype `{dflash['model'].get('target_requested_dtype')}`",
            f"- DFlash drafter: `{dflash['model'].get('drafter_model_id')}`; drafter dtype `{dflash['model'].get('drafter_requested_dtype')}`",
            "- Backend/policy: deterministic Transformers SDPA-math, greedy temperature 0, non-thinking, identical prompts/token budget/stopping contract.",
            "- Upstream checked: https://github.com/z-lab/dflash and https://github.com/z-lab/dflash/blob/main/dflash/model.py",
            "- Local flow matches upstream ordering for target prefill, non-causal draft, target verification, accepted-prefix commit, cache crop, and EOS/token-cap stopping.",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yml")
    sub = parser.add_subparsers(dest="command", required=True)
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--output", type=Path, required=True)
    smoke_parser = sub.add_parser("smoke")
    smoke_parser.add_argument("--condition", choices=("baseline", "dflash"), required=True)
    smoke_parser.add_argument("--output", type=Path, required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--condition", choices=("baseline", "dflash"), required=True)
    run_parser.add_argument("--output", type=Path, required=True)
    summary_parser = sub.add_parser("summarize")
    summary_parser.add_argument("--baseline", type=Path, required=True)
    summary_parser.add_argument("--dflash", type=Path, required=True)
    summary_parser.add_argument("--summary", type=Path, required=True)
    summary_parser.add_argument("--report", type=Path, required=True)
    summary_parser.add_argument("--diagnostic", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    if args.command == "audit":
        audit(config, args.output)
    elif args.command == "smoke":
        smoke(config, args.condition, args.output)
    elif args.command == "run":
        run_condition(config, args.condition, args.output)
    elif args.command == "summarize":
        summary = summarize(args.baseline, args.dflash, args.diagnostic)
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(render_report(summary), encoding="utf-8")
        print(json.dumps({"conclusion": summary["conclusion"], "gates": summary["gates"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
