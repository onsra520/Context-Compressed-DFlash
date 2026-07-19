"""Isolated Windows Baseline-AR vs DFlash-R1 canonical regression."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _worker(config_path: Path, condition: str, output: Path) -> None:
    if output.exists():
        raise RuntimeError(f"resume is disabled; worker output exists: {output}")
    os.environ.update({
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
    })
    from ccdf.config import load_config
    from ccdf.runtime.engine import RuntimeEngine
    from ccdf.validation.quality import evaluate_complete_answer

    config = load_config(config_path)
    if config.require("runtime.sdpa_kernel") != "math":
        raise RuntimeError("canonical regression requires math SDPA")
    if config.require("runtime.cuda_allocator_conf") is not None:
        raise RuntimeError("canonical Windows regression requires no CUDA allocator option")
    prompts = list(config.require("benchmark.prompts"))
    repetitions = int(config.require("benchmark.repetitions"))
    warmups = int(config.require("benchmark.warmup_requests"))
    max_new_tokens = int(config.require("runtime.max_new_tokens"))
    engine = RuntimeEngine(config, condition=condition)
    rows: list[dict[str, Any]] = []
    try:
        for warmup_index in range(warmups):
            engine.generate(
                prompts[warmup_index % len(prompts)],
                max_new_tokens=max_new_tokens,
                temperature=0.0,
            )
        for repetition in range(repetitions):
            for prompt_index, prompt in enumerate(prompts):
                encoded = engine.encode_prompt(prompt)
                input_ids = [int(value) for value in encoded.detach().cpu().reshape(-1).tolist()]
                result = engine.generate(
                    prompt,
                    max_new_tokens=max_new_tokens,
                    temperature=0.0,
                ).to_dict()
                quality = evaluate_complete_answer(
                    prompt_index=prompt_index,
                    text=result["text"],
                    stop_reason=result["stop_reason"],
                    output_tokens=result["output_tokens"],
                    max_new_tokens=max_new_tokens,
                ).to_dict()
                rows.append({
                    "condition": condition,
                    "prompt_index": prompt_index,
                    "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    "repetition": repetition,
                    "rendered_input_token_ids": input_ids,
                    "rendered_input_token_ids_sha256": hashlib.sha256(
                        json.dumps(input_ids, separators=(",", ":")).encode("utf-8")
                    ).hexdigest(),
                    "result": result,
                    "quality": quality,
                })
    finally:
        engine.close()
    _write_jsonl(output, rows)


def _canonical_reference(path: Path) -> dict[tuple[str, int], list[int]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    reference: dict[tuple[str, int], list[int]] = {}
    for row in payload["raw_runs"]:
        key = (str(row["condition"]), int(row["prompt_index"]))
        token_ids = [int(value) for value in row["result"]["generated_token_ids"]]
        if key in reference and reference[key] != token_ids:
            raise RuntimeError(f"canonical reference is nondeterministic: {key}")
        reference[key] = token_ids
    return reference


def _orchestrate(config_path: Path, artifact_root: Path) -> dict[str, Any]:
    from ccdf.config import load_config

    config = load_config(config_path)
    if artifact_root.exists():
        shutil.rmtree(artifact_root)
    (artifact_root / "raw_runs").mkdir(parents=True)
    (artifact_root / "worker_logs").mkdir()
    environment = os.environ.copy()
    environment.update({
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
    })
    attempts: list[dict[str, Any]] = []
    rows: dict[str, list[dict[str, Any]]] = {}
    for condition in ("baseline", "dflash"):
        output = artifact_root / "raw_runs" / f"{condition}.jsonl"
        command = [
            sys.executable,
            "-X",
            "faulthandler",
            str(Path(__file__).resolve()),
            "--config",
            str(config.path),
            "--condition-worker",
            condition,
            "--output",
            str(output),
        ]
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        stdout_path = artifact_root / "worker_logs" / f"{condition}.stdout.txt"
        stderr_path = artifact_root / "worker_logs" / f"{condition}.stderr.txt"
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        record = {
            "condition": condition,
            "attempt": 1,
            "retry_count": 0,
            "resume_enabled": False,
            "faulthandler_enabled": True,
            "command": command,
            "exit_code": completed.returncode,
            "signal": -completed.returncode if completed.returncode < 0 else None,
            "native_crash_code": (
                f"0x{completed.returncode & 0xFFFFFFFF:08X}"
                if completed.returncode not in (0, 1, 2) else None
            ),
            "duration_seconds": time.perf_counter() - started,
            "stdout_path": str(stdout_path.relative_to(artifact_root)),
            "stderr_path": str(stderr_path.relative_to(artifact_root)),
            "output_written": output.is_file(),
        }
        attempts.append(record)
        _write_json(artifact_root / "worker_attempts.json", attempts)
        if completed.returncode != 0 or not output.is_file():
            summary = {
                "status": "FAIL",
                "reason": f"{condition} worker exited {completed.returncode}; no retry",
                "worker_attempts": attempts,
            }
            _write_json(artifact_root / "summary.json", summary)
            return summary
        rows[condition] = _read_jsonl(output)

    reference_path = ROOT / "docs/artifacts/benchmark/canonical_freeze_benchmark.json"
    reference = _canonical_reference(reference_path)
    expected_per_condition = len(config.require("benchmark.prompts")) * int(
        config.require("benchmark.repetitions")
    )
    index = {
        (condition, int(row["prompt_index"]), int(row["repetition"])): row
        for condition, condition_rows in rows.items() for row in condition_rows
    }
    parity: list[dict[str, Any]] = []
    for repetition in range(int(config.require("benchmark.repetitions"))):
        for prompt_index in range(len(config.require("benchmark.prompts"))):
            baseline = index[("baseline", prompt_index, repetition)]
            dflash = index[("dflash", prompt_index, repetition)]
            parity.append({
                "prompt_index": prompt_index,
                "repetition": repetition,
                "rendered_input_match": baseline["rendered_input_token_ids"]
                == dflash["rendered_input_token_ids"],
                "generated_token_match": baseline["result"]["generated_token_ids"]
                == dflash["result"]["generated_token_ids"],
                "baseline_reference_match": baseline["result"]["generated_token_ids"]
                == reference[("baseline", prompt_index)],
                "dflash_reference_match": dflash["result"]["generated_token_ids"]
                == reference[("dflash", prompt_index)],
            })
    determinism = {
        condition: all(
            len({
                tuple(row["result"]["generated_token_ids"])
                for row in rows[condition] if int(row["prompt_index"]) == prompt_index
            }) == 1
            for prompt_index in range(len(config.require("benchmark.prompts")))
        )
        for condition in ("baseline", "dflash")
    }
    dflash_peaks = [
        int(row["result"]["memory"]["peak_reserved_bytes"])
        for row in rows["dflash"]
    ]
    structural_pass = all(
        all(item.get("structural_pass") is True for item in row["result"]["dflash"]["structural_audit"])
        for row in rows["dflash"]
    )
    gates = {
        "process_stability": len(attempts) == 2 and all(item["exit_code"] == 0 for item in attempts),
        "zero_retry": all(item["retry_count"] == 0 for item in attempts),
        "zero_resume": all(item["resume_enabled"] is False for item in attempts),
        "expected_run_count": all(len(rows[name]) == expected_per_condition for name in rows),
        "determinism": all(determinism.values()),
        "rendered_input_parity": all(item["rendered_input_match"] for item in parity),
        "generated_token_parity": all(item["generated_token_match"] for item in parity),
        "canonical_reference_parity": all(
            item["baseline_reference_match"] and item["dflash_reference_match"] for item in parity
        ),
        "quality": all(
            row["quality"]["quality_pass"]
            for condition_rows in rows.values() for row in condition_rows
        ),
        "dflash_structural": structural_pass,
        "dflash_peak_reserved_le_6_gib": max(dflash_peaks) <= 6 * 1024 ** 3,
    }
    summary = {
        "status": "PASS" if all(gates.values()) else "FAIL",
        "config_sha256": hashlib.sha256(config.path.read_bytes()).hexdigest(),
        "reference_path": str(reference_path),
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "sdpa_kernel": config.require("runtime.sdpa_kernel"),
        "sdpa_evidence": {
            "configured_policy": config.require("runtime.sdpa_kernel"),
            "resolved_profile": "frozen canonical root runtime",
            "effective_runtime_states": {
                condition: rows[condition][0]["result"]["runtime"]["determinism"]
                for condition in ("baseline", "dflash")
            },
            "actual_kernel_execution_observed_in_benchmark": False,
            "interpretation": (
                "effective_allowed_backends are dispatcher permissions, not proof that a kernel ran"
            ),
        },
        "fixed_block_size": config.require("optimization.block_policy.fixed_block_size"),
        "repetitions": config.require("benchmark.repetitions"),
        "run_counts": {condition: len(value) for condition, value in rows.items()},
        "pair_count": len(parity),
        "rendered_input_parity_count": sum(item["rendered_input_match"] for item in parity),
        "generated_token_parity_count": sum(item["generated_token_match"] for item in parity),
        "canonical_reference_parity_count": sum(
            item["baseline_reference_match"] and item["dflash_reference_match"] for item in parity
        ),
        "determinism": determinism,
        "max_dflash_peak_reserved_bytes": max(dflash_peaks),
        "worker_attempts": attempts,
        "gates": gates,
    }
    _write_json(artifact_root / "pair_parity.json", parity)
    _write_json(artifact_root / "resolved_config.json", config.data)
    _write_json(artifact_root / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("docs/artifacts/windows-environment-benchmark-rerun/canonical-regression"),
    )
    parser.add_argument("--condition-worker", choices=("baseline", "dflash"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.condition_worker:
        if args.output is None:
            parser.error("--condition-worker requires --output")
        _worker(args.config.resolve(), args.condition_worker, args.output.resolve())
        return
    summary = _orchestrate(args.config.resolve(), args.artifact_dir.resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
