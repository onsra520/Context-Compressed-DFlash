"""Tracked four-condition smoke workflow for the locked GSM8K and QMSum cohorts."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import signal
import statistics
import subprocess
import sys
import time
from typing import Any, Iterable, Mapping

import torch

from ..compression import CompressionConfig, ContextOnlyProtocol, LLMLinguaCompressor
from ..config import Config, load_config
from ..protocols.orchestrator import request_record
from ..runtime.device import GIB, configure_cuda_allocator_environment, synchronize
from ..runtime.engine import RuntimeEngine
from ..validation.environment import validate_environment
from .evaluators import (
    evaluate_gsm8k,
    evaluate_qmsum,
    qmsum_evidence_diagnostics,
    validate_evaluator_fixtures,
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _progress(message: str) -> None:
    print(f"[dataset-smoke] {message}", file=sys.stderr, flush=True)


class WatchdogTimeoutError(RuntimeError):
    """Raised after the watchdog has terminated an isolated worker tree."""

    def __init__(self, evidence: Mapping[str, Any]) -> None:
        self.evidence = dict(evidence)
        super().__init__(
            f"{self.evidence['reason']}: condition={self.evidence['condition']} "
            f"elapsed={self.evidence['condition_elapsed_seconds']:.3f}s"
        )


def _process_tree_snapshot(root_pid: int) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "root_pid": int(root_pid),
        "platform": sys.platform,
        "processes": [],
    }
    if sys.platform == "win32":
        script = (
            "$all=@(Get-CimInstance Win32_Process);"
            f"$ids=@({int(root_pid)});"
            "do{$before=$ids.Count;$ids+=@($all|Where-Object {$ids -contains $_.ParentProcessId}|"
            "ForEach-Object {[int]$_.ProcessId});$ids=@($ids|Sort-Object -Unique)}"
            "while($ids.Count -gt $before);"
            "$all|Where-Object {$ids -contains [int]$_.ProcessId}|"
            "Select-Object ProcessId,ParentProcessId,Name,CreationDate,KernelModeTime,"
            "UserModeTime,WorkingSetSize,CommandLine|ConvertTo-Json -Depth 3 -Compress"
        )
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                text=True,
                capture_output=True,
                check=False,
                timeout=10,
            )
            if completed.returncode == 0 and completed.stdout.strip():
                value = json.loads(completed.stdout)
                snapshot["processes"] = value if isinstance(value, list) else [value]
            else:
                snapshot["capture_error"] = completed.stderr.strip()
        except Exception as exc:
            snapshot["capture_error"] = f"{type(exc).__name__}: {exc}"
    else:
        snapshot["processes"] = [{"ProcessId": int(root_pid), "note": "root process only"}]
    try:
        gpu = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=timestamp,name,utilization.gpu,utilization.memory,memory.used,memory.total",
                "--format=csv,noheader",
            ],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        snapshot["gpu"] = {
            "exit_code": gpu.returncode,
            "stdout": gpu.stdout.strip(),
            "stderr": gpu.stderr.strip(),
        }
    except Exception as exc:
        snapshot["gpu"] = {"capture_error": f"{type(exc).__name__}: {exc}"}
    return snapshot


def _terminate_process_tree(
    process: subprocess.Popen[Any], terminate_grace_seconds: float
) -> dict[str, Any]:
    before = _process_tree_snapshot(process.pid)
    termination: dict[str, Any] = {"before": before, "method": None}
    if process.poll() is None:
        if sys.platform == "win32":
            completed = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                text=True,
                capture_output=True,
                check=False,
                timeout=max(5.0, terminate_grace_seconds),
            )
            termination.update({
                "method": "taskkill /T /F",
                "taskkill_exit_code": completed.returncode,
                "taskkill_stdout": completed.stdout.strip(),
                "taskkill_stderr": completed.stderr.strip(),
            })
        else:
            os.killpg(process.pid, signal.SIGTERM)
            termination["method"] = "SIGTERM process group"
        try:
            process.wait(timeout=terminate_grace_seconds)
        except subprocess.TimeoutExpired:
            if sys.platform == "win32":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)
            termination["forced_after_grace"] = True
    termination["exit_code"] = process.poll()
    termination["after"] = _process_tree_snapshot(process.pid)
    return termination


def _progress_signature(paths: Iterable[Path]) -> tuple[tuple[str, int, int], ...]:
    return tuple(
        (str(path), path.stat().st_size, path.stat().st_mtime_ns)
        for path in paths
        if path.is_file()
    )


def _watchdog_reason(
    *,
    now: float,
    workflow_started: float,
    condition_started: float,
    last_progress: float,
    settings: Mapping[str, Any],
) -> str | None:
    """Return the first config-owned watchdog limit exceeded at ``now``."""
    if now - workflow_started >= float(settings["dataset_wall_clock_timeout_seconds"]):
        return "dataset_wall_clock_timeout"
    if now - condition_started >= float(settings["condition_wall_clock_timeout_seconds"]):
        return "condition_wall_clock_timeout"
    if now - last_progress >= float(settings["no_progress_timeout_seconds"]):
        return "no_progress_timeout"
    return None


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(_canonical(dict(row)) + "\n" for row in rows), encoding="utf-8")


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_canonical(dict(row)) + "\n")
        handle.flush()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must be a JSON object")
            rows.append(value)
    return rows


def _cuda_memory(label: str) -> dict[str, Any]:
    synchronize()
    if not torch.cuda.is_available():
        return {"label": label, "cuda_available": False}
    return {
        "label": label,
        "cuda_available": True,
        "allocated_bytes": int(torch.cuda.memory_allocated()),
        "reserved_bytes": int(torch.cuda.memory_reserved()),
        "max_allocated_bytes": int(torch.cuda.max_memory_allocated()),
        "max_reserved_bytes": int(torch.cuda.max_memory_reserved()),
    }


def _require_full_context_cohorts(
    settings: Mapping[str, Any], expected_rows: int
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    paths = {
        dataset: Path(str(settings["cohorts"][dataset])).resolve()
        for dataset in ("gsm8k", "qmsum")
    }
    cohorts = {dataset: _read_jsonl(path) for dataset, path in paths.items()}
    evidence: dict[str, Any] = {"datasets": {}}
    for dataset, rows in cohorts.items():
        if len(rows) != expected_rows:
            raise ValueError(f"{dataset} cohort must contain {expected_rows} rows, found {len(rows)}")
        identifiers = [str(row.get("fixture_id", "")) for row in rows]
        if not all(identifiers) or len(set(identifiers)) != len(identifiers):
            raise ValueError(f"{dataset} cohort fixture IDs must be non-empty and unique")
        for row in rows:
            if row.get("dataset") != dataset:
                raise ValueError(f"cohort dataset mismatch for {row.get('fixture_id')}")
            parts = row.get("prompt_parts")
            if not isinstance(parts, dict) or parts.get("question") != row.get("question"):
                raise ValueError(f"invalid protected question for {row.get('fixture_id')}")
            if not parts.get("instruction") or not row.get("reference_answer"):
                raise ValueError(f"missing protected instruction/reference for {row.get('fixture_id')}")
            if dataset == "gsm8k" and parts.get("context") != "":
                raise ValueError(f"GSM8K context must be empty for {row.get('fixture_id')}")
            if dataset == "qmsum":
                truncation = row.get("truncation", {})
                if truncation.get("truncated") is not False:
                    raise ValueError(f"QMSum prefix truncation remains for {row.get('fixture_id')}")
                if truncation.get("strategy") != "full_transcript":
                    raise ValueError(f"QMSum row is not full_transcript: {row.get('fixture_id')}")
                if int(truncation.get("retained_words", -1)) != int(
                    truncation.get("original_words", -2)
                ):
                    raise ValueError(f"QMSum word coverage mismatch: {row.get('fixture_id')}")
        evidence["datasets"][dataset] = {
            "path": str(paths[dataset]),
            "sha256": _sha256_file(paths[dataset]),
            "rows": len(rows),
            "fixture_ids": identifiers,
            "source_row_hashes": [row.get("source_row_hash") for row in rows],
            "reference_answer_sha256": [
                _sha256_bytes(str(row["reference_answer"]).encode("utf-8")) for row in rows
            ],
        }
    manifest_path = Path(str(settings["cohorts"]["manifest"])).resolve()
    evidence["dataset_manifest"] = {
        "path": str(manifest_path),
        "sha256": _sha256_file(manifest_path),
        "value": json.loads(manifest_path.read_text(encoding="utf-8")),
    }
    selection_path = Path(str(settings["cohorts"]["selection_manifest"])).resolve()
    evidence["selection_manifest"] = {
        "path": str(selection_path),
        "sha256": _sha256_file(selection_path),
        "value": json.loads(selection_path.read_text(encoding="utf-8")),
    }
    return cohorts, evidence


def _protocol_for(row: Mapping[str, Any], settings: Mapping[str, Any]) -> ContextOnlyProtocol:
    dataset = str(row["dataset"])
    prompt_settings = settings["prompts"]
    return ContextOnlyProtocol(
        context=str(row["prompt_parts"]["context"]),
        question=str(row["prompt_parts"]["question"]),
        output_instruction=str(row["prompt_parts"]["instruction"]),
        context_header=str(prompt_settings[f"{dataset}_context_header"]),
        question_header=str(prompt_settings[f"{dataset}_question_header"]),
    )


def _protected_record(
    protocol: ContextOnlyProtocol, original_prompt: str, compressed_prompt: str
) -> dict[str, Any]:
    question = protocol.question.encode("utf-8")
    instruction = protocol.output_instruction.encode("utf-8")
    original_bytes = original_prompt.encode("utf-8")
    compressed_bytes = compressed_prompt.encode("utf-8")
    return {
        "question_sha256": _sha256_bytes(question),
        "instruction_sha256": _sha256_bytes(instruction),
        "question_byte_length": len(question),
        "instruction_byte_length": len(instruction),
        "question_present_once_original": original_bytes.count(question) == 1,
        "question_present_once_compressed": compressed_bytes.count(question) == 1,
        "instruction_present_once_original": original_bytes.count(instruction) == 1,
        "instruction_present_once_compressed": compressed_bytes.count(instruction) == 1,
        "pass": (
            original_bytes.count(question) == 1
            and compressed_bytes.count(question) == 1
            and original_bytes.count(instruction) == 1
            and compressed_bytes.count(instruction) == 1
        ),
    }


def _prepare_inputs(
    config: Config,
    settings: Mapping[str, Any],
    cohorts: Mapping[str, list[dict[str, Any]]],
    lifecycle: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    compression_settings = settings["compression"]
    compression_config = CompressionConfig(
        keep_rate=float(compression_settings["keep_rate"]),
        min_context_tokens=int(compression_settings["min_context_tokens"]),
        chunk_size_tokens=int(compression_settings["chunk_size_tokens"]),
        chunk_overlap_tokens=int(compression_settings["chunk_overlap_tokens"]),
        tokenizer=str(compression_settings["tokenizer"]),
        merge_policy=str(compression_settings["merge_policy"]),
    )
    lifecycle.append({"event": "before_compressor_load", "memory": _cuda_memory("before_compressor_load")})
    compressor = LLMLinguaCompressor(
        config.path_for("models.compressor.local_path"),
        device=str(config.require("models.compressor.device")),
        local_files_only=bool(config.require("runtime.local_files_only")),
        reserved_vram_budget_gib=float(config.require("models.compressor.reserved_budget_gib")),
    )
    stage_evidence = {
        "execution_mode": "staged",
        "initialization_ms": compressor.initialization_ms,
        "model_contract": dict(compressor.model_contract),
        "device_audit": dict(compressor.device_audit),
        "configured_compression": asdict(compression_config),
        "loaded_tokenizer": str(getattr(compressor.tokenizer, "name_or_path", compressor.model_path)),
        "after_load_memory": _cuda_memory("after_compressor_load"),
    }
    lifecycle.append({"event": "after_compressor_load", "memory": stage_evidence["after_load_memory"]})
    prepared: list[dict[str, Any]] = []
    try:
        for dataset in ("gsm8k", "qmsum"):
            for sample_index, row in enumerate(cohorts[dataset], start=1):
                _progress(f"compression {dataset} {sample_index}/{len(cohorts[dataset])}: {row['fixture_id']}")
                protocol = _protocol_for(row, settings)
                original_prompt = protocol.render(protocol.context)
                compression = compressor.compress(protocol, compression_config)
                compressed_prompt = protocol.render(compression.compressed_context)
                protected = _protected_record(protocol, original_prompt, compressed_prompt)
                compression_record = asdict(compression)
                compression_record["context_tokenizer"] = compression.chunk_tokenizer
                evidence = (
                    qmsum_evidence_diagnostics(
                        protocol.context,
                        str(row["reference_answer"]),
                        str(settings["evaluators"]["qmsum"]["word_pattern"]),
                    )
                    if dataset == "qmsum"
                    else {
                        "diagnostic_policy": "not_applicable_empty_context_numeric_dataset",
                        "reference_evidence_semantically_verified": False,
                    }
                )
                prepared.append({
                    "fixture_id": str(row["fixture_id"]),
                    "dataset": dataset,
                    "reference_answer": str(row["reference_answer"]),
                    "source_row_hash": row["source_row_hash"],
                    "content_hash": row["content_hash"],
                    "question": protocol.question,
                    "instruction": protocol.output_instruction,
                    "original_context_sha256": _sha256_bytes(protocol.context.encode("utf-8")),
                    "original_context": protocol.context,
                    "compressed_context": compression.compressed_context,
                    "original_prompt": original_prompt,
                    "compressed_prompt": compressed_prompt,
                    "original_prompt_sha256": _sha256_bytes(original_prompt.encode("utf-8")),
                    "compressed_prompt_sha256": _sha256_bytes(compressed_prompt.encode("utf-8")),
                    "compression": compression_record,
                    "protected_fields": protected,
                    "evidence_diagnostics": evidence,
                    "source_truncation": dict(row.get("truncation", {})),
                })
    finally:
        compressor.close()
        stage_evidence["after_close_memory"] = _cuda_memory("after_compressor_close")
        lifecycle.append({"event": "after_compressor_close", "memory": stage_evidence["after_close_memory"]})
    return prepared, stage_evidence


def _max_new_tokens(settings: Mapping[str, Any], dataset: str) -> int:
    return int(settings["generation"][f"{dataset}_max_new_tokens"])


def _single_generation_request(
    item: Mapping[str, Any],
    prompt_kind: str,
    settings: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Return the one final prompt allowed for a logical dataset sample."""
    if prompt_kind not in {"original", "compressed"}:
        raise ValueError(f"unsupported prompt kind: {prompt_kind}")
    dataset = str(item["dataset"])
    prompt = str(item[f"{prompt_kind}_prompt"])
    question = str(item["question"])
    instruction = str(item["instruction"])
    prompt_bytes = prompt.encode("utf-8")
    if prompt_bytes.count(question.encode("utf-8")) != 1:
        raise RuntimeError("single generation prompt must render the question exactly once")
    if prompt_bytes.count(instruction.encode("utf-8")) != 1:
        raise RuntimeError("single generation prompt must render the instruction exactly once")
    if dataset == "qmsum":
        generation = settings["generation"]
        if generation["qmsum_request_protocol"] != "single_final_generation":
            raise RuntimeError("QMSum request protocol is not single_final_generation")
        if generation["qmsum_original_context_overflow_policy"] != "fail":
            raise RuntimeError("QMSum original-context overflow policy is not fail")
    return prompt, {
        "protocol": "single_final_generation",
        "dataset": dataset,
        "prompt_kind": prompt_kind,
        "logical_sample_generation_requests": 1,
        "final_outputs_per_sample": 1,
        "output_concatenation": False,
        "max_new_tokens_scope": "one final generation output",
        "question_render_count": 1,
        "instruction_render_count": 1,
        "rendered_prompt_sha256": _sha256_bytes(prompt_bytes),
    }


def _error_rows(
    condition: str,
    runtime_condition: str,
    prompt_kind: str,
    prepared: Iterable[Mapping[str, Any]],
    error: Exception,
) -> list[dict[str, Any]]:
    message = f"{type(error).__name__}: {error}"
    rows = []
    for item in prepared:
        rows.append({
            "fixture_id": item["fixture_id"],
            "dataset": item["dataset"],
            "condition": condition,
            "runtime_condition": runtime_condition,
            "prompt_kind": prompt_kind,
            "repetition": 0,
            "success": False,
            "oom": "out of memory" in message.lower(),
            "error": message,
            "prompt_sha256": item[f"{prompt_kind}_prompt_sha256"],
            "original_prompt_sha256": item["original_prompt_sha256"],
            "compressed_prompt_sha256": item["compressed_prompt_sha256"],
            "source_row_hash": item["source_row_hash"],
            "content_hash": item["content_hash"],
            "protected_fields": item["protected_fields"],
            "compression": item["compression"],
            "source_truncation": item["source_truncation"],
            "evidence_diagnostics": item["evidence_diagnostics"],
            "run": {"success": False, "oom": "out of memory" in message.lower(), "error": message},
            "quality": None,
        })
    return rows


def _quality(
    record: Mapping[str, Any],
    item: Mapping[str, Any],
    settings: Mapping[str, Any],
) -> dict[str, Any] | None:
    if not record.get("success"):
        return None
    result = record["run"]["result"]
    cap_hit = bool(result["protocol_metrics"]["cap_hit"])
    if item["dataset"] == "gsm8k":
        return evaluate_gsm8k(
            str(result["text"]),
            str(item["reference_answer"]),
            settings["evaluators"]["gsm8k"],
            cap_hit=cap_hit,
        )
    return evaluate_qmsum(
        str(result["text"]),
        str(item["reference_answer"]),
        settings["evaluators"]["qmsum"],
        cap_hit=cap_hit,
        evidence_diagnostics=item["evidence_diagnostics"],
    )


def _run_conditions(
    config: Config,
    settings: Mapping[str, Any],
    prepared: list[dict[str, Any]],
    lifecycle: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    warmups = int(settings["generation"]["warmup_requests"])
    repetitions = int(settings["generation"]["repetitions"])
    for condition_spec in settings["conditions"]:
        condition = str(condition_spec["name"])
        prompt_kind = str(condition_spec["prompt_kind"])
        runtime_condition = str(condition_spec["runtime_condition"])
        _progress(f"loading condition {condition} ({runtime_condition}, {prompt_kind})")
        lifecycle.append({"event": "before_condition_load", "condition": condition, "memory": _cuda_memory(f"before_{condition}_load")})
        try:
            engine = RuntimeEngine(config, condition=runtime_condition)
        except Exception as exc:
            rows.extend(_error_rows(condition, runtime_condition, prompt_kind, prepared, exc))
            lifecycle.append({"event": "condition_load_error", "condition": condition, "error": f"{type(exc).__name__}: {exc}", "memory": _cuda_memory(f"{condition}_load_error")})
            continue
        lifecycle.append({"event": "after_condition_load", "condition": condition, "memory": _cuda_memory(f"after_{condition}_load")})
        try:
            prompt_key = f"{prompt_kind}_prompt"
            for warmup_index in range(warmups):
                warmup_item = prepared[warmup_index % len(prepared)]
                request_record(
                    condition=condition,
                    prompt_kind=prompt_kind,
                    prompt=str(warmup_item[prompt_key]),
                    compression=dict(warmup_item["compression"]),
                    engine=engine,
                    lifecycle=lifecycle,
                    max_new_tokens=_max_new_tokens(settings, str(warmup_item["dataset"])),
                    temperature=float(config.require("runtime.temperature")),
                    dataset=str(warmup_item["dataset"]),
                    measured=False,
                )
            for repetition in range(repetitions):
                for request_index, item in enumerate(prepared, start=1):
                    _progress(
                        f"condition {condition} repetition {repetition + 1}/{repetitions} "
                        f"request {request_index}/{len(prepared)}: {item['dataset']}/{item['fixture_id']}"
                    )
                    prompt, request_contract = _single_generation_request(
                        item, prompt_kind, settings
                    )
                    run = request_record(
                        condition=condition,
                        prompt_kind=prompt_kind,
                        prompt=prompt,
                        compression=dict(item["compression"]),
                        engine=engine,
                        lifecycle=lifecycle,
                        max_new_tokens=_max_new_tokens(settings, str(item["dataset"])),
                        temperature=float(config.require("runtime.temperature")),
                        dataset=str(item["dataset"]),
                        measured=True,
                        context_overflow_error_code=(
                            "ORIGINAL_CONTEXT_EXCEEDS_MODEL_LIMIT"
                            if item["dataset"] == "qmsum" and prompt_kind == "original"
                            else "COMPRESSED_CONTEXT_EXCEEDS_MODEL_LIMIT"
                            if item["dataset"] == "qmsum"
                            else None
                        ),
                    )
                    record: dict[str, Any] = {
                        "fixture_id": item["fixture_id"],
                        "dataset": item["dataset"],
                        "condition": condition,
                        "runtime_condition": runtime_condition,
                        "prompt_kind": prompt_kind,
                        "repetition": repetition,
                        "success": bool(run.get("success")),
                        "oom": bool(run.get("oom", False)),
                        "error": run.get("error"),
                        "prompt_sha256": item[f"{prompt_kind}_prompt_sha256"],
                        "original_prompt_sha256": item["original_prompt_sha256"],
                        "compressed_prompt_sha256": item["compressed_prompt_sha256"],
                        "source_row_hash": item["source_row_hash"],
                        "content_hash": item["content_hash"],
                        "protected_fields": item["protected_fields"],
                        "compression": item["compression"],
                        "source_truncation": item["source_truncation"],
                        "evidence_diagnostics": item["evidence_diagnostics"],
                        "generation_request_contract": request_contract,
                        "run": run,
                    }
                    record["quality"] = _quality(record, item, settings)
                    rows.append(record)
        finally:
            engine.close()
            lifecycle.append({"event": "after_condition_close", "condition": condition, "memory": _cuda_memory(f"after_{condition}_close")})
    return rows


def _condition_worker(
    config: Config,
    settings: Mapping[str, Any],
    prepared: list[dict[str, Any]],
    condition_name: str,
    rows_path: Path,
    progress_path: Path,
) -> None:
    condition_spec = next(
        (item for item in settings["conditions"] if str(item["name"]) == condition_name),
        None,
    )
    if condition_spec is None:
        raise ValueError(f"unknown condition worker name: {condition_name}")
    if rows_path.exists():
        raise RuntimeError(f"resume is disabled; worker output already exists: {rows_path}")
    if progress_path.exists():
        raise RuntimeError(f"resume is disabled; worker progress already exists: {progress_path}")
    completed: set[tuple[str, int]] = set()
    repetitions = int(settings["generation"]["repetitions"])
    expected = len(prepared) * repetitions
    condition = str(condition_spec["name"])
    prompt_kind = str(condition_spec["prompt_kind"])
    runtime_condition = str(condition_spec["runtime_condition"])
    lifecycle: list[dict[str, Any]] = []
    worker_started = time.perf_counter()
    _append_jsonl(progress_path, {
        "event": "model_load_start",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "condition": condition,
        "dataset": None,
        "sample_index": None,
        "input_tokens": None,
        "output_tokens": None,
        "elapsed_sample_seconds": None,
        "total_elapsed_seconds": 0.0,
    })
    _progress(
        f"worker loading fresh condition {condition} ({runtime_condition}, {prompt_kind}); "
        f"resume disabled, expected rows {expected}"
    )
    engine = RuntimeEngine(config, condition=runtime_condition)
    try:
        _append_jsonl(progress_path, {
            "event": "model_load_complete",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "condition": condition,
            "dataset": None,
            "sample_index": None,
            "input_tokens": None,
            "output_tokens": None,
            "elapsed_sample_seconds": None,
            "total_elapsed_seconds": time.perf_counter() - worker_started,
        })
        prompt_key = f"{prompt_kind}_prompt"

        def execute_request(
            item: Mapping[str, Any], prompt: str, *, measured: bool, sample_index: int
        ) -> dict[str, Any]:
            sample_started = time.perf_counter()
            encoded = engine.encode_prompt(prompt)
            input_tokens = int(encoded.numel())
            del encoded
            _append_jsonl(progress_path, {
                "event": "request_start",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "condition": condition,
                "dataset": str(item["dataset"]),
                "sample_index": sample_index,
                "fixture_id": str(item["fixture_id"]),
                "measured": measured,
                "input_tokens": input_tokens,
                "output_tokens": None,
                "elapsed_sample_seconds": 0.0,
                "total_elapsed_seconds": time.perf_counter() - worker_started,
            })
            run = request_record(
                condition=condition,
                prompt_kind=prompt_kind,
                prompt=prompt,
                compression=dict(item["compression"]),
                engine=engine,
                lifecycle=lifecycle,
                max_new_tokens=_max_new_tokens(settings, str(item["dataset"])),
                temperature=float(config.require("runtime.temperature")),
                dataset=str(item["dataset"]),
                measured=measured,
                context_overflow_error_code=(
                    "ORIGINAL_CONTEXT_EXCEEDS_MODEL_LIMIT"
                    if item["dataset"] == "qmsum" and prompt_kind == "original"
                    else "COMPRESSED_CONTEXT_EXCEEDS_MODEL_LIMIT"
                    if item["dataset"] == "qmsum"
                    else None
                ),
            )
            result = run.get("result", {})
            metrics = result.get("protocol_metrics", {})
            _append_jsonl(progress_path, {
                "event": "request_complete" if run.get("success") else "request_error",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "condition": condition,
                "dataset": str(item["dataset"]),
                "sample_index": sample_index,
                "fixture_id": str(item["fixture_id"]),
                "measured": measured,
                "input_tokens": input_tokens,
                "output_tokens": metrics.get("output_tokens"),
                "elapsed_sample_seconds": time.perf_counter() - sample_started,
                "total_elapsed_seconds": time.perf_counter() - worker_started,
                "decode_tok_s": metrics.get("decode_tok_s"),
                "cap_hit": metrics.get("cap_hit"),
                "error": run.get("error"),
            })
            return run

        warmups = int(settings["generation"]["warmup_requests"])
        for warmup_index in range(warmups):
            warmup_item = prepared[warmup_index % len(prepared)]
            execute_request(
                warmup_item,
                str(warmup_item[prompt_key]),
                measured=False,
                sample_index=warmup_index + 1,
            )
        for repetition in range(repetitions):
            for request_index, item in enumerate(prepared, start=1):
                identity = (str(item["fixture_id"]), repetition)
                _progress(
                    f"worker {condition} repetition {repetition + 1}/{repetitions} "
                    f"request {request_index}/{len(prepared)}: {item['dataset']}/{item['fixture_id']}"
                )
                prompt, request_contract = _single_generation_request(
                    item, prompt_kind, settings
                )
                run = execute_request(
                    item, prompt, measured=True, sample_index=request_index
                )
                record: dict[str, Any] = {
                    "fixture_id": item["fixture_id"],
                    "dataset": item["dataset"],
                    "condition": condition,
                    "runtime_condition": runtime_condition,
                    "prompt_kind": prompt_kind,
                    "repetition": repetition,
                    "success": bool(run.get("success")),
                    "oom": bool(run.get("oom", False)),
                    "error": run.get("error"),
                    "prompt_sha256": item[f"{prompt_kind}_prompt_sha256"],
                    "original_prompt_sha256": item["original_prompt_sha256"],
                    "compressed_prompt_sha256": item["compressed_prompt_sha256"],
                    "source_row_hash": item["source_row_hash"],
                    "content_hash": item["content_hash"],
                    "protected_fields": item["protected_fields"],
                    "compression": item["compression"],
                    "source_truncation": item["source_truncation"],
                    "evidence_diagnostics": item["evidence_diagnostics"],
                    "generation_request_contract": request_contract,
                    "run": run,
                }
                record["quality"] = _quality(record, item, settings)
                _append_jsonl(rows_path, record)
                completed.add(identity)
    finally:
        engine.close()
        _append_jsonl(progress_path, {
            "event": "model_unload_complete",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "condition": condition,
            "dataset": None,
            "sample_index": None,
            "input_tokens": None,
            "output_tokens": None,
            "elapsed_sample_seconds": None,
            "total_elapsed_seconds": time.perf_counter() - worker_started,
        })
    if len(completed) != expected:
        raise RuntimeError(f"condition worker {condition} wrote {len(completed)}/{expected} rows")


def _run_conditions_isolated(
    source_config: Config,
    settings: Mapping[str, Any],
    prepared: list[dict[str, Any]],
    artifact_root: Path,
    workflow_started: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    working = artifact_root / ".working"
    working.mkdir(parents=True, exist_ok=True)
    prepared_path = working / "prepared.jsonl"
    _write_jsonl(prepared_path, prepared)
    attempts: list[dict[str, Any]] = []
    max_attempts = int(settings["generation"]["condition_worker_max_attempts"])
    if max_attempts != 1:
        raise RuntimeError("clean dataset smoke requires condition_worker_max_attempts=1")
    log_root = artifact_root / "worker_logs"
    log_root.mkdir(parents=True, exist_ok=True)
    progress_root = artifact_root / "progress_logs"
    progress_root.mkdir(parents=True, exist_ok=True)
    watchdog = settings["watchdog"]
    dataset_timeout = float(watchdog["dataset_wall_clock_timeout_seconds"])
    condition_timeout = float(watchdog["condition_wall_clock_timeout_seconds"])
    no_progress_timeout = float(watchdog["no_progress_timeout_seconds"])
    poll_interval = float(watchdog["poll_interval_seconds"])
    terminate_grace = float(watchdog["terminate_grace_seconds"])
    all_rows: list[dict[str, Any]] = []
    for condition_spec in settings["conditions"]:
        condition = str(condition_spec["name"])
        rows_path = working / f"{condition}.jsonl"
        progress_path = progress_root / f"{condition}.jsonl"
        command = [
            sys.executable,
            "-X",
            "faulthandler",
            "-m",
            "ccdf.benchmark.dataset_smoke",
            "--config",
            str(source_config.path),
            "--condition-worker",
            condition,
            "--prepared-path",
            str(prepared_path),
            "--rows-path",
            str(rows_path),
            "--progress-path",
            str(progress_path),
        ]
        _progress(f"starting isolated condition {condition}, single attempt")
        environment = os.environ.copy()
        environment.update({
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "PYTHONUNBUFFERED": "1",
        })
        stdout_path = log_root / f"{condition}.stdout.txt"
        stderr_path = log_root / f"{condition}.stderr.txt"
        started = time.perf_counter()
        with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr_handle:
            popen_kwargs: dict[str, Any] = {
                "cwd": source_config.root,
                "env": environment,
                "text": True,
                "stdout": stdout_handle,
                "stderr": stderr_handle,
            }
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                popen_kwargs["start_new_session"] = True
            process = subprocess.Popen(command, **popen_kwargs)
            watched_paths = (rows_path, progress_path)
            signature = _progress_signature(watched_paths)
            last_progress = time.perf_counter()
            timeout_reason: str | None = None
            while process.poll() is None:
                now = time.perf_counter()
                updated = _progress_signature(watched_paths)
                if updated != signature:
                    signature = updated
                    last_progress = now
                timeout_reason = _watchdog_reason(
                    now=now,
                    workflow_started=workflow_started,
                    condition_started=started,
                    last_progress=last_progress,
                    settings=watchdog,
                )
                if timeout_reason is not None:
                    termination = _terminate_process_tree(process, terminate_grace)
                    break
                time.sleep(poll_interval)
            exit_code = process.poll()
        duration = time.perf_counter() - started
        record = {
            "condition": condition,
            "attempt": 1,
            "max_attempts": 1,
            "retry_count": 0,
            "resume_enabled": False,
            "faulthandler_enabled": True,
            "command": command,
            "exit_code": exit_code,
            "signal": -exit_code if isinstance(exit_code, int) and exit_code < 0 else None,
            "native_crash_code": (
                f"0x{exit_code & 0xFFFFFFFF:08X}"
                if isinstance(exit_code, int) and exit_code not in (0, 1, 2) else None
            ),
            "duration_seconds": duration,
            "rows_written": len(_read_jsonl(rows_path)) if rows_path.is_file() else 0,
            "stdout_path": str(stdout_path.relative_to(artifact_root)),
            "stderr_path": str(stderr_path.relative_to(artifact_root)),
            "progress_path": str(progress_path.relative_to(artifact_root)),
            "timeout_event": timeout_reason,
        }
        attempts.append(record)
        _write_json(artifact_root / "condition_worker_attempts.partial.json", attempts)
        if timeout_reason is not None:
            progress_rows = _read_jsonl(progress_path) if progress_path.is_file() else []
            evidence = {
                "status": "TIMEOUT_FAIL",
                "reason": timeout_reason,
                "condition": condition,
                "condition_elapsed_seconds": duration,
                "dataset_elapsed_seconds": time.perf_counter() - workflow_started,
                "configured_timeouts_seconds": {
                    "dataset": dataset_timeout,
                    "condition": condition_timeout,
                    "no_progress": no_progress_timeout,
                },
                "rows_written": record["rows_written"],
                "last_progress": progress_rows[-1] if progress_rows else None,
                "last_progress_file_timestamp_utc": (
                    datetime.fromtimestamp(progress_path.stat().st_mtime, timezone.utc).isoformat()
                    if progress_path.is_file() else None
                ),
                "termination": termination,
                "attempts": attempts,
            }
            _write_json(artifact_root / "watchdog_failure.json", evidence)
            _write_json(artifact_root / "condition_worker_attempts.json", attempts)
            raise WatchdogTimeoutError(evidence)
        if exit_code != 0:
            raise RuntimeError(
                f"isolated condition {condition} exited {exit_code}; no retry"
            )
        all_rows.extend(_read_jsonl(rows_path))
    return all_rows, attempts


def _metric_valid(record: Mapping[str, Any]) -> tuple[bool, list[str]]:
    if not record.get("success"):
        return False, ["unsuccessful_run"]
    result = record["run"]["result"]
    reasons: list[str] = []
    for section, names in {
        "timing": ("target_prefill_ms", "decode_total_ms", "generation_total_ms", "warm_request_ms"),
        "memory": ("peak_allocated_bytes", "peak_reserved_bytes"),
        "metrics": ("decode_tok_s", "generation_tok_s"),
    }.items():
        for name in names:
            value = result.get(section, {}).get(name)
            if not isinstance(value, (int, float)) or value < 0:
                reasons.append(f"invalid_{section}_{name}")
    protocol = result.get("protocol_metrics", {})
    for name in (
        "compression_latency_ms", "prefill_latency_ms", "decode_latency_ms",
        "generation_latency_ms", "stage_sum_warm_e2e_ms", "request_wall_clock_ms",
        "output_tokens", "decode_tok_s",
    ):
        value = protocol.get(name)
        if not isinstance(value, (int, float)) or value < 0:
            reasons.append(f"invalid_protocol_{name}")
    chat = protocol.get("chat_template_input", {})
    if not isinstance(chat.get("token_ids"), list) or chat.get("token_count") != len(chat.get("token_ids", [])):
        reasons.append("invalid_rendered_input_token_ids")
    if record["runtime_condition"] == "dflash":
        for name in ("effective_tau", "draft_acceptance_rate", "target_forwards_per_output_token"):
            value = result.get("dflash", {}).get(name)
            if not isinstance(value, (int, float)) or value < 0:
                reasons.append(f"invalid_dflash_{name}")
    return not reasons, reasons


def _enrich_token_metrics(rows: list[dict[str, Any]]) -> None:
    index = {(row["fixture_id"], row["condition"]): row for row in rows}
    for row in rows:
        original = index.get((row["fixture_id"], "baseline-ar"))
        compressed = index.get((row["fixture_id"], "llmlingua-ar-r2"))
        original_count = (
            original["run"]["result"]["protocol_metrics"]["chat_template_input"]["token_count"]
            if original and original.get("success")
            else None
        )
        compressed_count = (
            compressed["run"]["result"]["protocol_metrics"]["chat_template_input"]["token_count"]
            if compressed and compressed.get("success")
            else None
        )
        reduction = (
            1 - compressed_count / original_count
            if original_count and compressed_count is not None
            else None
        )
        if row["dataset"] == "gsm8k" and reduction is not None and reduction != 0:
            reduction = None
        row["token_metrics"] = {
            "original_context_tokens": int(row["compression"]["original_tokens"]),
            "compressed_context_tokens": int(row["compression"]["compressed_tokens"]),
            "context_reduction_rate": (
                0.0 if row["dataset"] == "gsm8k" else row["compression"]["reduction_rate"]
            ),
            "original_rendered_input_tokens": original_count,
            "compressed_rendered_input_tokens": compressed_count,
            "rendered_input_reduction_rate": reduction,
            "gsm8k_compression_effectiveness_claimed": False if row["dataset"] == "gsm8k" else None,
        }
        row["metric_valid"], row["metric_invalid_reasons"] = _metric_valid(row)


def _first_token_divergence(left: list[int], right: list[int]) -> dict[str, Any] | None:
    for index, (left_token, right_token) in enumerate(zip(left, right)):
        if left_token != right_token:
            return {
                "token_index": index,
                "left_token_id": left_token,
                "right_token_id": right_token,
                "left_output_length": len(left),
                "right_output_length": len(right),
            }
    if len(left) != len(right):
        index = min(len(left), len(right))
        return {
            "token_index": index,
            "left_token_id": left[index] if index < len(left) else None,
            "right_token_id": right[index] if index < len(right) else None,
            "left_output_length": len(left),
            "right_output_length": len(right),
        }
    return None


def _pair_parity(rows: list[dict[str, Any]], settings: Mapping[str, Any]) -> dict[str, Any]:
    index = {(row["fixture_id"], row["condition"]): row for row in rows}
    records: list[dict[str, Any]] = []
    for pair in settings["parity_pairs"]:
        for dataset in ("gsm8k", "qmsum"):
            fixture_ids = sorted({row["fixture_id"] for row in rows if row["dataset"] == dataset})
            for fixture_id in fixture_ids:
                left = index[(fixture_id, str(pair["left"]))]
                right = index[(fixture_id, str(pair["right"]))]
                if left.get("success") and right.get("success"):
                    left_result = left["run"]["result"]
                    right_result = right["run"]["result"]
                    left_input = left_result["protocol_metrics"]["chat_template_input"]["token_ids"]
                    right_input = right_result["protocol_metrics"]["chat_template_input"]["token_ids"]
                    left_input_chunks = left_result["protocol_metrics"]["chat_template_input"].get("chunk_token_ids", [left_input])
                    right_input_chunks = right_result["protocol_metrics"]["chat_template_input"].get("chunk_token_ids", [right_input])
                    left_output = left_result["generated_token_ids"]
                    right_output = right_result["generated_token_ids"]
                    input_match = left_input == right_input and left_input_chunks == right_input_chunks
                    output_match = left_output == right_output
                    record = {
                        "pair": pair["name"], "dataset": dataset, "fixture_id": fixture_id,
                        "left": pair["left"], "right": pair["right"],
                        "both_success": True,
                        "input_token_ids_match": input_match,
                        "generated_token_ids_match": output_match,
                        "input_chunk_boundaries_match": left_input_chunks == right_input_chunks,
                        "left_input_token_ids_sha256": _sha256_bytes(_canonical(left_input).encode("utf-8")),
                        "right_input_token_ids_sha256": _sha256_bytes(_canonical(right_input).encode("utf-8")),
                        "left_generated_token_ids_sha256": _sha256_bytes(_canonical(left_output).encode("utf-8")),
                        "right_generated_token_ids_sha256": _sha256_bytes(_canonical(right_output).encode("utf-8")),
                        "first_generated_token_divergence": _first_token_divergence(
                            left_output, right_output
                        ),
                    }
                else:
                    record = {
                        "pair": pair["name"], "dataset": dataset, "fixture_id": fixture_id,
                        "left": pair["left"], "right": pair["right"],
                        "both_success": False,
                        "input_token_ids_match": False,
                        "generated_token_ids_match": False,
                    }
                records.append(record)
    total = len(records)
    return {
        "records": records,
        "pairs": total,
        "input_token_parity_count": sum(record["input_token_ids_match"] for record in records),
        "generated_token_parity_count": sum(record["generated_token_ids_match"] for record in records),
        "input_token_parity_rate": sum(record["input_token_ids_match"] for record in records) / total if total else 0.0,
        "generated_token_parity_rate": sum(record["generated_token_ids_match"] for record in records) / total if total else 0.0,
    }


def _median(values: Iterable[float]) -> float | None:
    materialized = list(values)
    return statistics.median(materialized) if materialized else None


def _condition_summaries(rows: list[dict[str, Any]], settings: Mapping[str, Any]) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for condition_spec in settings["conditions"]:
        condition = str(condition_spec["name"])
        selected = [row for row in rows if row["condition"] == condition]
        successful = [row for row in selected if row.get("success")]
        results = [row["run"]["result"] for row in successful]
        summary: dict[str, Any] = {
            "runs": len(selected),
            "successful_runs": len(successful),
            "p50_prefill_ms": _median(result["timing"]["target_prefill_ms"] for result in results),
            "p50_decode_ms": _median(result["timing"]["decode_total_ms"] for result in results),
            "p50_generation_ms": _median(result["timing"]["generation_total_ms"] for result in results),
            "p50_stage_sum_e2e_ms": _median(result["protocol_metrics"]["stage_sum_warm_e2e_ms"] for result in results),
            "p50_synchronized_request_ms": _median(result["protocol_metrics"]["request_wall_clock_ms"] for result in results),
            "total_output_tokens": sum(int(result["output_tokens"]) for result in results),
            "p50_decode_tok_s": _median(result["metrics"]["decode_tok_s"] for result in results),
            "peak_allocated_vram_bytes": max((int(result["protocol_metrics"]["full_request_peak_vram"]["peak_allocated_bytes"]) for result in results), default=None),
            "peak_reserved_vram_bytes": max((int(result["protocol_metrics"]["full_request_peak_vram"]["peak_reserved_bytes"]) for result in results), default=None),
            "cap_hits": sum(bool(result["protocol_metrics"]["cap_hit"]) for result in results),
            "oom_events": sum(bool(row.get("oom")) for row in selected),
            "error_events": sum(not bool(row.get("success")) for row in selected),
        }
        if str(condition_spec["runtime_condition"]) == "dflash":
            summary["dflash"] = {
                "p50_effective_tau": _median(result["dflash"]["effective_tau"] for result in results),
                "p50_acceptance_rate": _median(result["dflash"]["draft_acceptance_rate"] for result in results),
                "p50_target_forwards_per_output_token": _median(result["dflash"]["target_forwards_per_output_token"] for result in results),
            }
        summaries[condition] = summary
    return summaries


def _gate_matrix(
    rows: list[dict[str, Any]],
    prepared: list[dict[str, Any]],
    parity: Mapping[str, Any],
    summaries: Mapping[str, Any],
    settings: Mapping[str, Any],
    evaluator_lock: Mapping[str, Any],
) -> dict[str, Any]:
    gates = settings["hard_gates"]
    successful = sum(bool(row.get("success")) for row in rows)
    protected_pass = sum(bool(item["protected_fields"]["pass"]) for item in prepared)
    protected_rate = protected_pass / len(prepared) if prepared else 0.0
    metric_count = sum(bool(row.get("metric_valid")) for row in rows)
    metric_rate = metric_count / len(rows) if rows else 0.0
    qmsum_items = [item for item in prepared if item["dataset"] == "qmsum"]
    qmsum_rows = [row for row in rows if row["dataset"] == "qmsum"]
    coverage_rate = (
        sum(float(item["compression"]["coverage_rate"]) for item in qmsum_items) / len(qmsum_items)
        if qmsum_items else 0.0
    )
    hidden_truncated = sum(int(item["compression"]["hidden_truncated_tokens"]) for item in prepared)
    evaluator_sample_valid: dict[str, int] = {}
    for dataset in ("gsm8k", "qmsum"):
        fixture_ids = {row["fixture_id"] for row in rows if row["dataset"] == dataset}
        evaluator_sample_valid[dataset] = sum(
            all(
                (row.get("quality") or {}).get("valid") is True
                for row in rows
                if row["dataset"] == dataset and row["fixture_id"] == fixture_id
            )
            for fixture_id in fixture_ids
        )
    oom_events = sum(bool(row.get("oom")) for row in rows)
    error_events = sum(not bool(row.get("success")) for row in rows)
    request_counts = sorted({
        int(row.get("run", {}).get("logical_sample_generation_requests", 0))
        for row in qmsum_rows
    })
    final_output_counts = sorted({
        int(row.get("run", {}).get("final_outputs_per_sample", 0))
        for row in qmsum_rows
    })
    output_concatenation_disabled = bool(qmsum_rows) and all(
        row.get("run", {}).get("output_concatenation") is False
        for row in qmsum_rows
    )
    entries = [
        {"gate": "successful_condition_runs", "actual": successful, "required": int(gates["successful_condition_runs"]), "pass": successful == int(gates["successful_condition_runs"])},
        {"gate": "logical_sample_generation_requests", "actual_values": request_counts, "required": int(gates["logical_sample_generation_requests"]), "pass": request_counts == [int(gates["logical_sample_generation_requests"])]},
        {"gate": "final_outputs_per_sample", "actual_values": final_output_counts, "required": int(gates["final_outputs_per_sample"]), "pass": final_output_counts == [int(gates["final_outputs_per_sample"])]},
        {"gate": "output_concatenation_disabled", "actual": output_concatenation_disabled, "required": True, "pass": output_concatenation_disabled},
        {"gate": "pair_input_token_parity_rate", "actual": parity["input_token_parity_rate"], "required": float(gates["pair_input_token_parity_rate"]), "pass": parity["input_token_parity_rate"] >= float(gates["pair_input_token_parity_rate"])},
        {"gate": "pair_generated_token_parity_rate", "actual": parity["generated_token_parity_rate"], "required": float(gates["pair_generated_token_parity_rate"]), "pass": parity["generated_token_parity_rate"] >= float(gates["pair_generated_token_parity_rate"])},
        {"gate": "protected_fields_rate", "actual": protected_rate, "required": float(gates["protected_fields_rate"]), "pass": protected_rate >= float(gates["protected_fields_rate"])},
        {"gate": "gsm8k_evaluator_valid_count", "actual": evaluator_sample_valid["gsm8k"], "required": int(gates["gsm8k_evaluator_valid_count"]), "pass": evaluator_sample_valid["gsm8k"] == int(gates["gsm8k_evaluator_valid_count"])},
        {"gate": "qmsum_evaluator_valid_count", "actual": evaluator_sample_valid["qmsum"], "required": int(gates["qmsum_evaluator_valid_count"]), "pass": evaluator_sample_valid["qmsum"] == int(gates["qmsum_evaluator_valid_count"])},
        {"gate": "qmsum_precompression_coverage_rate", "actual": coverage_rate, "required": float(gates["qmsum_precompression_coverage_rate"]), "pass": coverage_rate >= float(gates["qmsum_precompression_coverage_rate"])},
        {"gate": "hidden_truncated_tokens", "actual": hidden_truncated, "required": int(gates["hidden_truncated_tokens"]), "pass": hidden_truncated == int(gates["hidden_truncated_tokens"])},
        {"gate": "metric_validity_rate", "actual": metric_rate, "required": float(gates["metric_validity_rate"]), "pass": metric_rate >= float(gates["metric_validity_rate"])},
        {"gate": "max_oom_events", "actual": oom_events, "required": int(gates["max_oom_events"]), "pass": oom_events <= int(gates["max_oom_events"])},
        {"gate": "max_error_events", "actual": error_events, "required": int(gates["max_error_events"]), "pass": error_events <= int(gates["max_error_events"])},
        {"gate": "evaluator_fixture_lock", "actual": evaluator_lock["pass"], "required": True, "pass": evaluator_lock["pass"] is True},
    ]
    memory_limit = float(gates["dflash_peak_reserved_vram_gib"])
    for condition in ("dflash-r1", "cc-dflash-r2"):
        peak_bytes = summaries[condition]["peak_reserved_vram_bytes"]
        peak_gib = peak_bytes / GIB if peak_bytes is not None else None
        entries.append({
            "gate": f"{condition}_peak_reserved_vram_gib",
            "actual": peak_gib,
            "required_max": memory_limit,
            "pass": peak_gib is not None and peak_gib <= memory_limit,
        })
    return {
        "pass": all(entry["pass"] for entry in entries),
        "entries": entries,
        "counts": {
            "runs": len(rows), "successful": successful, "protected_samples": protected_pass,
            "metric_valid_runs": metric_count, "gsm8k_valid_samples": evaluator_sample_valid["gsm8k"],
            "qmsum_valid_samples": evaluator_sample_valid["qmsum"], "oom_events": oom_events,
            "error_events": error_events, "hidden_truncated_tokens": hidden_truncated,
            "qmsum_rows_with_one_generation_request": sum(
                row.get("run", {}).get("logical_sample_generation_requests") == 1
                for row in qmsum_rows
            ),
            "qmsum_rows_with_one_final_output": sum(
                row.get("run", {}).get("final_outputs_per_sample") == 1
                for row in qmsum_rows
            ),
        },
    }


def _quality_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for dataset in ("gsm8k", "qmsum"):
        selected = [row for row in rows if row["dataset"] == dataset and row.get("quality")]
        if dataset == "gsm8k":
            summary[dataset] = {
                "evaluations": len(selected),
                "correct": sum(row["quality"]["label"] == "correct" for row in selected),
                "wrong_numeric": sum(row["quality"]["label"] == "wrong_numeric" for row in selected),
                "invalid_format": sum(row["quality"]["label"] == "invalid_format" for row in selected),
                "missing_answer": sum(row["quality"]["label"] == "missing_answer" for row in selected),
                "cap_hit": sum(row["quality"]["label"] == "cap_hit" for row in selected),
                "accuracy": sum(row["quality"]["correct"] for row in selected) / len(selected) if selected else None,
                "metric": "normalized_numeric_equality",
            }
        else:
            summary[dataset] = {
                "evaluations": len(selected),
                "valid": sum(row["quality"]["valid"] for row in selected),
                "mean_reference_recall_proxy": statistics.fmean(row["quality"]["reference_recall"] for row in selected) if selected else None,
                "mean_reference_precision_proxy": statistics.fmean(row["quality"]["reference_precision"] for row in selected) if selected else None,
                "cap_hits": sum(row["quality"]["cap_hit"] for row in selected),
                "semantic_correctness": "NOT_CLAIMED",
            }
    return summary


def _cap_hit_breakdown(
    rows: list[dict[str, Any]], settings: Mapping[str, Any]
) -> dict[str, Any]:
    records = []
    for dataset in ("gsm8k", "qmsum"):
        configured_limit = _max_new_tokens(settings, dataset)
        for condition_spec in settings["conditions"]:
            condition = str(condition_spec["name"])
            selected = [
                row
                for row in rows
                if row["dataset"] == dataset and row["condition"] == condition
            ]
            cap_hits = sum(
                bool(row.get("success"))
                and bool(row["run"]["result"]["protocol_metrics"]["cap_hit"])
                for row in selected
            )
            records.append({
                "dataset": dataset,
                "condition": condition,
                "configured_max_new_tokens": configured_limit,
                "runs": len(selected),
                "cap_hits": cap_hits,
                "outputs_complete_before_cap": len(selected) - cap_hits,
                "evaluator_scope": "generated_output_only",
                "cap_hit_is_complete_output": False,
            })
    return {
        "records": records,
        "by_dataset": {
            dataset: {
                "configured_max_new_tokens": _max_new_tokens(settings, dataset),
                "runs": sum(
                    record["runs"] for record in records if record["dataset"] == dataset
                ),
                "cap_hits": sum(
                    record["cap_hits"] for record in records if record["dataset"] == dataset
                ),
            }
            for dataset in ("gsm8k", "qmsum")
        },
    }


def _source_identity(root: Path) -> dict[str, Any]:
    source_paths = [
        root / "src/ccdf/benchmark/dataset_smoke.py",
        root / "src/ccdf/benchmark/dataset_smoke_verify.py",
        root / "src/ccdf/benchmark/evaluators.py",
        root / "src/ccdf/compression/llmlingua.py",
        root / "src/ccdf/compression/schemas.py",
        root / "src/ccdf/protocols/orchestrator.py",
        root / "src/ccdf/runtime/determinism.py",
        root / "src/ccdf/config.py",
    ]
    return {str(path.relative_to(root)): _sha256_file(path) for path in source_paths}


def _import_origins() -> dict[str, Any]:
    names = ("ccdf", "torch", "transformers", "llmlingua", "yaml")
    origins = {}
    for name in names:
        module = importlib.import_module(name)
        origins[name] = str(getattr(module, "__file__", None))
    return {"python_executable": sys.executable, "modules": origins}


def _artifact_manifest(root: Path) -> dict[str, Any]:
    files = sorted(path for path in root.rglob("*") if path.is_file() and path.name != "artifact_manifest.json")
    return {
        "manifest_version": "dataset-smoke-artifacts.v1",
        "files": [
            {"path": str(path.relative_to(root)), "sha256": _sha256_file(path), "bytes": path.stat().st_size}
            for path in files
        ],
    }


def run_dataset_smoke(source_config: Config, *, replace: bool = False) -> dict[str, Any]:
    """Run the config-owned n10 workflow after validating configuration first."""
    source_config.validate(require_model_files=False)
    profile = source_config.resolve_dataset_smoke_profile()
    config = profile.config
    settings = profile.settings
    configure_cuda_allocator_environment(config.require("runtime.cuda_allocator_conf"))
    if {
        str(config.require("memory.compressor_residency_mode")),
        str(config.require("memory.generation_residency_mode")),
    } != {"staged"}:
        raise RuntimeError("dataset smoke requires staged compressor/generation residency")
    evaluator_lock = validate_evaluator_fixtures(settings["evaluators"])
    if not evaluator_lock["pass"]:
        raise RuntimeError(f"evaluator fixture lock failed: {evaluator_lock}")
    environment = validate_environment(config)
    if not torch.cuda.is_available():
        raise RuntimeError("dataset smoke requires CUDA")
    expected_rows = int(settings["cohorts"]["expected_rows_per_dataset"])
    cohorts, cohort_evidence = _require_full_context_cohorts(settings, expected_rows)
    _progress("configuration, environment, evaluator fixtures, and cohorts validated")

    artifact_root = Path(str(settings["artifact_directory"])).resolve()
    forbidden = {
        config.path_for("benchmark.output_jsonl").parent,
        source_config.resolve_active_protocol_profile().path_for("artifact_directory"),
    }
    if artifact_root in forbidden:
        raise RuntimeError(f"dataset smoke artifact path overlaps a canonical/profile artifact: {artifact_root}")
    if artifact_root.exists():
        if not replace:
            raise FileExistsError(f"artifact directory already exists: {artifact_root}")
        shutil.rmtree(artifact_root)
    artifact_root.mkdir(parents=True)

    started_at_utc = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    lifecycle: list[dict[str, Any]] = [{"event": "workflow_start", "memory": _cuda_memory("workflow_start")}]
    prepared, compression_stage = _prepare_inputs(config, settings, cohorts, lifecycle)
    _progress("compression stage complete; generation stages starting")
    try:
        dataset_timeout = float(settings["watchdog"]["dataset_wall_clock_timeout_seconds"])
        if time.perf_counter() - started >= dataset_timeout:
            raise WatchdogTimeoutError({
                "status": "TIMEOUT_FAIL",
                "reason": "dataset_wall_clock_timeout",
                "condition": "preparation",
                "condition_elapsed_seconds": time.perf_counter() - started,
                "dataset_elapsed_seconds": time.perf_counter() - started,
                "configured_timeouts_seconds": {
                    "dataset": dataset_timeout,
                    "condition": float(settings["watchdog"]["condition_wall_clock_timeout_seconds"]),
                    "no_progress": float(settings["watchdog"]["no_progress_timeout_seconds"]),
                },
                "rows_written": 0,
                "last_progress": None,
                "termination": None,
                "attempts": [],
            })
        rows, worker_attempts = _run_conditions_isolated(
            source_config, settings, prepared, artifact_root, started
        )
    except WatchdogTimeoutError as exc:
        failure = exc.evidence
        lifecycle.append({
            "event": "watchdog_timeout",
            "reason": failure["reason"],
            "condition": failure["condition"],
            "memory": _cuda_memory("watchdog_timeout_parent"),
        })
        worker_attempts = list(failure.get("attempts", []))
        gate_entries = [
            {
                "gate": "timeout_events",
                "actual": 1,
                "required_max": int(settings["hard_gates"]["max_timeout_events"]),
                "pass": False,
            },
            {
                "gate": "no_progress_timeouts",
                "actual": int(failure["reason"] == "no_progress_timeout"),
                "required_max": int(settings["hard_gates"]["max_no_progress_timeouts"]),
                "pass": failure["reason"] != "no_progress_timeout",
            },
            {
                "gate": "retry_events",
                "actual": sum(int(item.get("retry_count", 0)) for item in worker_attempts),
                "required_max": int(settings["hard_gates"]["max_retry_events"]),
                "pass": all(int(item.get("retry_count", 0)) == 0 for item in worker_attempts),
            },
            {
                "gate": "resume_events",
                "actual": sum(bool(item.get("resume_enabled")) for item in worker_attempts),
                "required_max": int(settings["hard_gates"]["max_resume_events"]),
                "pass": all(item.get("resume_enabled") is False for item in worker_attempts),
            },
            {
                "gate": "crash_events",
                "actual": sum(bool(item.get("signal") or item.get("native_crash_code")) for item in worker_attempts),
                "required_max": int(settings["hard_gates"]["max_crash_events"]),
                "pass": sum(
                    bool(item.get("signal") or item.get("native_crash_code"))
                    for item in worker_attempts
                ) <= int(settings["hard_gates"]["max_crash_events"]),
            },
        ]
        gate_matrix = {
            "pass": False,
            "verdict": "TIMEOUT_FAIL",
            "entries": gate_entries,
            "counts": {
                "runs": sum(int(item.get("rows_written", 0)) for item in worker_attempts),
                "timeout_events": 1,
                "no_progress_timeouts": int(failure["reason"] == "no_progress_timeout"),
                "retry_events": gate_entries[2]["actual"],
                "resume_events": gate_entries[3]["actual"],
                "crash_events": gate_entries[4]["actual"],
            },
        }
        summary = {
            "workflow_version": settings["version"],
            "status": "TIMEOUT_FAIL",
            "started_at_utc": started_at_utc,
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": time.perf_counter() - started,
            "config_sha256": profile.source_config_sha256,
            "resolved_profile": profile.name,
            "gate_pass": False,
            "native_process_stability_pass": False,
            "benchmark_gate_verdict_pass": False,
            "watchdog_failure": failure,
            "condition_workers": {
                "attempts": len(worker_attempts),
                "retries": gate_entries[2]["actual"],
                "all_conditions_completed": False,
            },
        }
        _write_json(artifact_root / "resolved_config.json", profile.snapshot())
        _write_json(artifact_root / "environment.json", {"validation": environment, "import_origins": _import_origins()})
        _write_json(artifact_root / "cohort_manifest.json", cohort_evidence)
        _write_json(artifact_root / "evaluator_lock.json", evaluator_lock)
        _write_json(artifact_root / "compression_stage.json", compression_stage)
        _write_json(artifact_root / "lifecycle.json", lifecycle)
        _write_json(artifact_root / "condition_worker_attempts.json", worker_attempts)
        _write_json(artifact_root / "watchdog_failure.json", failure)
        _write_json(artifact_root / "gate_matrix.json", gate_matrix)
        _write_json(artifact_root / "summary.json", summary)
        _write_json(artifact_root / "artifact_manifest.json", _artifact_manifest(artifact_root))
        _progress(f"workflow sealed with TIMEOUT_FAIL: {failure['reason']}")
        return summary
    _enrich_token_metrics(rows)
    parity = _pair_parity(rows, settings)
    condition_summaries = _condition_summaries(rows, settings)
    gate_matrix = _gate_matrix(rows, prepared, parity, condition_summaries, settings, evaluator_lock)
    lifecycle.append({"event": "workflow_complete", "memory": _cuda_memory("workflow_complete")})
    duration_seconds = time.perf_counter() - started
    timeout_events = sum(bool(item.get("timeout_event")) for item in worker_attempts)
    no_progress_timeouts = sum(
        item.get("timeout_event") == "no_progress_timeout" for item in worker_attempts
    )
    retry_events = sum(int(item.get("retry_count", 0)) for item in worker_attempts)
    resume_events = sum(bool(item.get("resume_enabled")) for item in worker_attempts)
    crash_events = sum(
        bool(item.get("signal") or item.get("native_crash_code")) for item in worker_attempts
    )
    safety_entries = [
        {"gate": "dataset_wall_clock_seconds", "actual": duration_seconds, "required_max": float(settings["watchdog"]["dataset_wall_clock_timeout_seconds"]), "pass": duration_seconds <= float(settings["watchdog"]["dataset_wall_clock_timeout_seconds"])},
        {"gate": "timeout_events", "actual": timeout_events, "required_max": int(settings["hard_gates"]["max_timeout_events"]), "pass": timeout_events <= int(settings["hard_gates"]["max_timeout_events"])},
        {"gate": "no_progress_timeouts", "actual": no_progress_timeouts, "required_max": int(settings["hard_gates"]["max_no_progress_timeouts"]), "pass": no_progress_timeouts <= int(settings["hard_gates"]["max_no_progress_timeouts"])},
        {"gate": "retry_events", "actual": retry_events, "required_max": int(settings["hard_gates"]["max_retry_events"]), "pass": retry_events <= int(settings["hard_gates"]["max_retry_events"])},
        {"gate": "resume_events", "actual": resume_events, "required_max": int(settings["hard_gates"]["max_resume_events"]), "pass": resume_events <= int(settings["hard_gates"]["max_resume_events"])},
        {"gate": "crash_events", "actual": crash_events, "required_max": int(settings["hard_gates"]["max_crash_events"]), "pass": crash_events <= int(settings["hard_gates"]["max_crash_events"])},
    ]
    gate_matrix["entries"].extend(safety_entries)
    gate_matrix["pass"] = gate_matrix["pass"] and all(item["pass"] for item in safety_entries)
    gate_matrix["counts"].update({
        "timeout_events": timeout_events,
        "no_progress_timeouts": no_progress_timeouts,
        "retry_events": retry_events,
        "resume_events": resume_events,
        "crash_events": crash_events,
    })

    source_hashes = _source_identity(config.root)
    evaluator_source_path = config.root / "src/ccdf/benchmark/evaluators.py"
    evaluator_config_hash = _sha256_bytes(_canonical(settings["evaluators"]).encode("utf-8"))
    effective_states = []
    for row in rows:
        if row.get("success"):
            result = row["run"]["result"]
            effective_states.append({
                "condition": row["condition"],
                "fixture_id": row["fixture_id"],
                "determinism": result["runtime"]["determinism"],
                "model_attention": {
                    key: value for key, value in result["model"].items() if "attention" in key
                },
            })
    sdpa_evidence = {
        "config_sha256": profile.source_config_sha256,
        "configured": {
            "attention_backend": source_config.require("runtime.attention_backend"),
            "sdpa_kernel": source_config.require("runtime.sdpa_kernel"),
        },
        "resolved_profile": profile.name,
        "resolved": {
            "attention_backend": config.require("runtime.attention_backend"),
            "sdpa_kernel": config.require("runtime.sdpa_kernel"),
        },
        "effective_runtime_states": effective_states,
        "interpretation": (
            "flash_sdp_enabled and mem_efficient_sdp_enabled describe dispatcher availability only; "
            "they are not evidence that either kernel executed"
        ),
        "actual_kernel_execution_observed": False,
    }
    cap_hit_breakdown = _cap_hit_breakdown(rows, settings)
    native_process_stability_pass = (
        len(worker_attempts) == len(settings["conditions"])
        and all(int(item["exit_code"]) == 0 for item in worker_attempts)
        and all(item.get("signal") is None for item in worker_attempts)
        and all(item.get("native_crash_code") is None for item in worker_attempts)
        and all(int(item.get("retry_count", -1)) == 0 for item in worker_attempts)
    )
    summary = {
        "workflow_version": settings["version"],
        "status": "PASS" if gate_matrix["pass"] else "FAIL",
        "started_at_utc": started_at_utc,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": duration_seconds,
        "config_sha256": profile.source_config_sha256,
        "resolved_profile": profile.name,
        "generation_limits": {
            dataset: _max_new_tokens(settings, dataset) for dataset in ("gsm8k", "qmsum")
        },
        "cap_hits": cap_hit_breakdown["by_dataset"],
        "counts": gate_matrix["counts"],
        "pair_parity": {key: value for key, value in parity.items() if key != "records"},
        "quality": _quality_summary(rows),
        "conditions": condition_summaries,
        "qmsum_compression": {
            "samples": sum(item["dataset"] == "qmsum" for item in prepared),
            "mean_context_reduction_rate": statistics.fmean(
                item["compression"]["reduction_rate"] for item in prepared if item["dataset"] == "qmsum"
            ),
            "coverage_rate": statistics.fmean(
                item["compression"]["coverage_rate"] for item in prepared if item["dataset"] == "qmsum"
            ),
            "hidden_truncated_tokens": sum(
                item["compression"]["hidden_truncated_tokens"] for item in prepared if item["dataset"] == "qmsum"
            ),
        },
        "gsm8k_boundary": {
            "samples": sum(item["dataset"] == "gsm8k" for item in prepared),
            "all_empty_context": all(
                item["compression"]["original_tokens"] == 0 for item in prepared if item["dataset"] == "gsm8k"
            ),
            "all_compression_no_op": all(
                item["compression"]["no_op_reason"] == "empty_context" for item in prepared if item["dataset"] == "gsm8k"
            ),
            "compression_effectiveness_claimed": False,
        },
        "gate_pass": gate_matrix["pass"],
        "native_process_stability_pass": native_process_stability_pass,
        "benchmark_gate_verdict_pass": gate_matrix["pass"],
        "condition_workers": {
            "attempts": len(worker_attempts),
            "retries": retry_events,
            "nonzero_exits": sum(int(item["exit_code"]) != 0 for item in worker_attempts),
            "timeouts": timeout_events,
            "no_progress_timeouts": no_progress_timeouts,
            "resumes": resume_events,
            "crashes": crash_events,
            "all_conditions_completed": all(
                any(
                    item["condition"] == str(condition["name"])
                    and int(item["exit_code"]) == 0
                    for item in worker_attempts
                )
                for condition in settings["conditions"]
            ),
        },
    }

    _write_json(artifact_root / "resolved_config.json", profile.snapshot())
    _write_json(artifact_root / "environment.json", {"validation": environment, "import_origins": _import_origins()})
    _write_json(artifact_root / "sdpa_evidence.json", sdpa_evidence)
    _write_json(artifact_root / "cohort_manifest.json", cohort_evidence)
    _write_json(artifact_root / "evaluator_lock.json", {
        **evaluator_lock,
        "versions": {dataset: settings["evaluators"][dataset]["version"] for dataset in ("gsm8k", "qmsum")},
        "source_sha256": _sha256_file(evaluator_source_path),
        "config_sha256": evaluator_config_hash,
        "prior_qmsum_contract": "set(lowercase([A-Za-z0-9]+)); overlap precision and recall",
    })
    _write_json(artifact_root / "compression_stage.json", compression_stage)
    _write_jsonl(artifact_root / "qmsum_chunk_maps.jsonl", (
        {
            "fixture_id": item["fixture_id"],
            "original_context_tokens": item["compression"]["original_tokens"],
            "chunk_count": item["compression"]["chunk_count"],
            "chunk_token_ranges": item["compression"]["chunk_token_ranges"],
            "compressed_tokens_by_chunk": item["compression"]["compressed_tokens_by_chunk"],
            "covered_unique_tokens": item["compression"]["covered_unique_tokens"],
            "coverage_rate": item["compression"]["coverage_rate"],
            "dropped_tokens": item["compression"]["dropped_tokens"],
            "hidden_truncated_tokens": item["compression"]["hidden_truncated_tokens"],
            "evidence_diagnostics": item["evidence_diagnostics"],
        }
        for item in prepared if item["dataset"] == "qmsum"
    ))
    _write_jsonl(artifact_root / "prepared_input_manifest.jsonl", (
        {
            key: value
            for key, value in item.items()
            if key not in {
                "original_prompt", "compressed_prompt", "original_context",
                "compressed_context", "question", "instruction",
            }
        }
        for item in prepared
    ))
    for dataset in ("gsm8k", "qmsum"):
        for condition in (str(item["name"]) for item in settings["conditions"]):
            _write_jsonl(
                artifact_root / "raw_runs" / dataset / f"{condition}.jsonl",
                (row for row in rows if row["dataset"] == dataset and row["condition"] == condition),
            )
    _write_jsonl(artifact_root / "per_sample_results.jsonl", rows)
    _write_jsonl(artifact_root / "qmsum_generation_requests.jsonl", (
        {
            "fixture_id": row["fixture_id"],
            "condition": row["condition"],
            "prompt_kind": row["prompt_kind"],
            "request_contract": row.get("generation_request_contract"),
            "logical_sample_generation_requests": row.get("run", {}).get(
                "logical_sample_generation_requests", 0
            ),
            "final_outputs_per_sample": row.get("run", {}).get(
                "final_outputs_per_sample", 0
            ),
            "output_concatenation": row.get("run", {}).get(
                "output_concatenation", False
            ),
            "rendered_input": row.get("run", {}).get("result", {}).get(
                "protocol_metrics", {}
            ).get("chat_template_input"),
            "model_context_limit": row.get("run", {}).get("result", {}).get(
                "protocol_metrics", {}
            ).get("model_context_limit"),
        }
        for row in rows if row["dataset"] == "qmsum"
    ))
    _write_json(artifact_root / "pair_parity.json", parity)
    _write_json(artifact_root / "condition_summaries.json", condition_summaries)
    _write_json(artifact_root / "cap_hit_breakdown.json", cap_hit_breakdown)
    _write_json(artifact_root / "gate_matrix.json", gate_matrix)
    _write_json(artifact_root / "lifecycle.json", lifecycle)
    _write_json(artifact_root / "condition_worker_attempts.json", worker_attempts)
    _write_json(artifact_root / "source_hashes.json", source_hashes)
    _write_json(artifact_root / "summary.json", summary)
    shutil.rmtree(artifact_root / ".working", ignore_errors=True)
    _write_json(artifact_root / "artifact_manifest.json", _artifact_manifest(artifact_root))
    _progress(f"workflow complete with status {summary['status']}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--condition-worker")
    parser.add_argument("--prepared-path", type=Path)
    parser.add_argument("--rows-path", type=Path)
    parser.add_argument("--progress-path", type=Path)
    args = parser.parse_args()
    source_config = load_config(args.config)
    if args.condition_worker is not None:
        if args.prepared_path is None or args.rows_path is None or args.progress_path is None:
            parser.error(
                "--condition-worker requires --prepared-path, --rows-path, and --progress-path"
            )
        source_config.validate(require_model_files=False)
        profile = source_config.resolve_dataset_smoke_profile()
        configure_cuda_allocator_environment(
            profile.config.require("runtime.cuda_allocator_conf")
        )
        _condition_worker(
            profile.config,
            profile.settings,
            _read_jsonl(args.prepared_path.resolve()),
            args.condition_worker,
            args.rows_path.resolve(),
            args.progress_path.resolve(),
        )
        return
    summary = run_dataset_smoke(source_config, replace=args.replace)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
