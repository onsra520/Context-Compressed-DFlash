#!/usr/bin/env python3
"""Read-only frozen-contract preflight for the final n20 benchmark."""

from __future__ import annotations

import hashlib
import inspect
import json
import platform
from pathlib import Path
import subprocess
import sys

import torch

from ccdf.config import load_config
from ccdf.datasets import load_canonical_samples
from ccdf.datasets.qmsum_context import select_query_aware_context


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/final-benchmark-n20"
FROZEN_INSTRUCTION = (
    "Solve with concise equations. Track all quantities, steps, and units; do not skip "
    "conversions or repeated actions. End with: Final answer: <number>"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def model_identity(profile: dict) -> dict:
    return {
        key: profile[key]
        for key in ("model_id", "local_path", "quantization", "dtype")
        if key in profile
    }


def main() -> int:
    config = load_config(ROOT / "config.yml")
    sample_manifest = json.loads((OUT / "SAMPLE-MANIFEST.json").read_text(encoding="utf-8"))
    gsm_path = ROOT / sample_manifest["datasets"]["gsm8k"]["sample_file"]
    qmsum_path = ROOT / sample_manifest["datasets"]["qmsum"]["sample_file"]
    gsm = load_canonical_samples(gsm_path, expected_dataset="gsm8k")
    qmsum = load_canonical_samples(qmsum_path, expected_dataset="qmsum")
    prior_manifest = json.loads(
        (ROOT / "docs/reviews/12-gsm8k-v5-four-condition/run-manifest.json").read_text(encoding="utf-8")
    )
    old_v4_cache = read_jsonl(
        ROOT / "docs/reviews/10-quality-repair-gsm8k-qmsum-n10/gsm8k/compression/cache.jsonl"
    )
    final_cache_paths = [
        OUT / "gsm8k/compression-cache.jsonl",
        OUT / "qmsum/compression-cache.jsonl",
    ]
    gpu = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu",
            "--format=csv,noheader",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    processes = subprocess.run(
        [
            "nvidia-smi",
            "--query-compute-apps=pid,process_name,used_memory",
            "--format=csv,noheader",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    checks = {
        "config_matches_promoted_v5_run": sha256(ROOT / "config.yml") == prior_manifest["config_sha256"],
        "gsm8k_instruction_v5_frozen": config.require("prompts.gsm8k_instruction") == FROZEN_INSTRUCTION
        and all(row["metadata"]["instruction"] == FROZEN_INSTRUCTION for row in gsm),
        "runtime_seed_42": config.require("runtime.seed") == 42,
        "runtime_temperature_zero": float(config.require("runtime.temperature")) == 0.0,
        "runtime_sdpa_math": config.require("runtime.attention_backend") == "sdpa"
        and config.require("runtime.sdpa_kernel") == "math",
        "runtime_thinking_disabled": config.require("runtime.enable_thinking") is False,
        "generation_limits_frozen": config.require("dataset_smoke.generation.gsm8k_max_new_tokens") == 256
        and config.require("dataset_smoke.generation.qmsum_max_new_tokens") == 512
        and config.require("dataset_smoke.generation.warmup_requests") == 1
        and config.require("dataset_smoke.generation.repetitions") == 1,
        "model_identities_frozen": dict(prior_manifest["models"])
        == {
            "baseline": model_identity(config.require("models.baseline")),
            "dflash_target": model_identity(config.require("models.dflash.target")),
            "dflash_drafter": model_identity(config.require("models.dflash.drafter")),
        },
        "compressor_requests_cuda": str(config.require("models.compressor.device")).startswith("cuda"),
        "cuda_available": torch.cuda.is_available() and torch.cuda.device_count() == 1,
        "gpu_query_healthy": gpu.returncode == 0,
        "gpu_compute_owner_free": processes.returncode == 0 and not processes.stdout.strip(),
        "deterministic_n20_counts": len(gsm) == len(qmsum) == 20
        and len({row["sample_id"] for row in gsm}) == len({row["sample_id"] for row in qmsum}) == 20,
        "sample_files_match_manifest": sha256(gsm_path) == sample_manifest["datasets"]["gsm8k"]["sample_file_sha256"]
        and sha256(qmsum_path) == sample_manifest["datasets"]["qmsum"]["sample_file_sha256"],
        "n10_prefix_preserved": [row["sample_id"] for row in gsm[:10]] == prior_manifest["workload"]["sample_ids"],
        "selection_does_not_accept_reference": "reference" not in inspect.signature(select_query_aware_context).parameters,
        "qmsum_query_aware_evidence_complete": all(
            row["metadata"]["context_selection"]["policy"] == "query_aware_budgeted"
            and row["metadata"]["context_selection"]["selected_context_sha256"]
            and row["metadata"]["context_selection"]["selected_chunk_ids"]
            for row in qmsum
        ),
        "fresh_final_cache_paths": all(not path.exists() for path in final_cache_paths),
        "gsm8k_not_v4_prompt_hashes": not (
            {hashlib.sha256(row["prompt"].encode("utf-8")).hexdigest() for row in gsm}
            & {row["original_prompt_sha256"] for row in old_v4_cache}
        ),
    }
    environment = {
        "schema": "ccdf.final-benchmark-n20.environment.v1",
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_count": torch.cuda.device_count(),
        "cuda_device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "nvidia_smi_gpu": gpu.stdout.strip().splitlines(),
        "nvidia_smi_compute_processes": processes.stdout.strip().splitlines(),
        "config_sha256": sha256(ROOT / "config.yml"),
        "source_sha256": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in (
                ROOT / "src/ccdf/benchmark/four_condition/runner.py",
                ROOT / "src/ccdf/benchmark/four_condition/audit.py",
                ROOT / "src/ccdf/compression/llmlingua.py",
                ROOT / "src/ccdf/compression/safeguard.py",
                ROOT / "src/ccdf/datasets/pipeline.py",
                ROOT / "src/ccdf/datasets/qmsum_context.py",
                ROOT / "src/ccdf/evaluation/datasets.py",
                ROOT / "src/ccdf/dflash/verifier.py",
            )
        },
    }
    payload = {
        "schema": "ccdf.final-benchmark-n20.preflight.v1",
        "pass": all(checks.values()),
        "checks": checks,
        "gpu": environment["nvidia_smi_gpu"],
        "compute_processes": environment["nvidia_smi_compute_processes"],
        "sample_file_sha256": {
            "gsm8k": sha256(gsm_path),
            "qmsum": sha256(qmsum_path),
        },
    }
    (OUT / "ENVIRONMENT.json").write_text(json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "preflight.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
