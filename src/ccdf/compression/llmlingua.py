"""Strict GPU-only LLMLingua-2 prompt compression."""

from __future__ import annotations

import gc
import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import torch

from ..config import Rec2Config
from ..core.errors import ModelContractError
from ..infrastructure.device import collect_memory, reset_peak_memory, synchronize
from .safeguard import safeguard_prompt_batch

SCHEMA = "ccdf.compression-cache.v2"


def adaptive_keep_rate(config: Rec2Config, target_user_tokens: int) -> float:
    if target_user_tokens < 0:
        raise ValueError("target-user token count cannot be negative")
    policy = dict(config.require("dataset_smoke.compression.adaptive_keep_rate"))
    if not policy.get("enabled"):
        raise ValueError("adaptive compression policy must be enabled")
    if target_user_tokens <= int(policy["short_max_target_user_tokens"]):
        return float(policy["short_keep_rate"])
    if target_user_tokens <= int(policy["medium_max_target_user_tokens"]):
        return float(policy["medium_keep_rate"])
    return float(policy["long_keep_rate"])


def compression_success_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "successful_compressions": sum(
            row.get("status") == "success" and row.get("compression_applied") is True
            for row in rows
        ),
        "fallback_samples": sum(row.get("status") == "fallback" for row in rows),
        "failed_samples": sum(row.get("status") == "failed" for row in rows),
    }


def run_safeguarded_attempts(
    text: str,
    rates: list[float],
    compress_at_rate: Any,
) -> tuple[Any | None, list[dict[str, Any]]]:
    """Run ordered safety attempts; return None to signal explicit fallback."""
    attempts: list[dict[str, Any]] = []
    for rate in rates:
        result = safeguard_prompt_batch(text, lambda values: compress_at_rate(values, rate))
        validation = result.validation.to_dict()
        attempts.append(
            {
                "keep_rate": rate,
                "fact_validation_passed": validation["passed"],
                "failure_reasons": list(validation["failure_reasons"]),
            }
        )
        if validation["passed"]:
            return result, attempts
    return None, attempts


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _device_index(requested: str) -> int:
    if not requested.startswith("cuda"):
        raise ModelContractError(f"compressor requested device must be CUDA, got {requested!r}")
    return int(requested.split(":", 1)[1]) if ":" in requested else torch.cuda.current_device()


def _placement(model: Any, *, expected_index: int) -> tuple[str, list[str]]:
    tensors = [*model.parameters(), *model.buffers()]
    if not tensors:
        raise ModelContractError("compressor has no parameters or buffers")
    devices = sorted({str(tensor.device) for tensor in tensors})
    forbidden = [device for device in devices if device != f"cuda:{expected_index}"]
    if forbidden:
        raise ModelContractError(
            f"compressor is not fully resident on cuda:{expected_index}; observed {devices}"
        )
    dtypes = sorted(
        {str(tensor.dtype).removeprefix("torch.") for tensor in tensors if tensor.is_floating_point()}
    )
    return devices[0], dtypes


def _close(compressor: Any | None) -> None:
    if compressor is not None:
        compressor.model = None
        compressor.tokenizer = None
    del compressor
    gc.collect()
    if torch.cuda.is_available():
        synchronize()
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()


def _canonical_budget(config: Rec2Config) -> float:
    model_budget = float(config.require("models.compressor.reserved_budget_gib"))
    memory_budget = float(config.require("memory.compressor_reserved_budget_gib"))
    if model_budget != memory_budget:
        raise ModelContractError(
            "compressor reserved budget conflict: "
            f"models.compressor={model_budget} GiB memory={memory_budget} GiB"
        )
    return memory_budget


def _token_count(tokenizer: Any, text: str) -> int:
    encoded = tokenizer(text, add_special_tokens=False)
    ids = encoded["input_ids"] if isinstance(encoded, dict) else encoded.input_ids
    if ids and isinstance(ids[0], list):
        ids = ids[0]
    return len(ids)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _row_sha256(row: dict[str, Any]) -> str:
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _checkpoint_path(output_path: Path) -> Path:
    return output_path.with_suffix(output_path.suffix + ".checksums.jsonl")


def _append_checkpoint(path: Path, row: dict[str, Any]) -> None:
    payload = {
        "schema": "ccdf.compression-cache.row-checksum.v1",
        "sample_id": str(row["sample_id"]),
        "row_sha256": _row_sha256(row),
    }
    append_jsonl(path, payload)


def _load_resume_rows(output_path: Path, samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not output_path.exists() or output_path.stat().st_size == 0:
        return []
    rows = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    sample_ids = [str(sample["sample_id"]) for sample in samples]
    row_ids = [str(row["sample_id"]) for row in rows]
    if row_ids != sample_ids[: len(row_ids)]:
        raise ValueError("resume compression rows are not an ordered sample prefix")
    if len(row_ids) != len(set(row_ids)):
        raise ValueError("resume compression rows contain duplicate sample IDs")
    run_ids = {str(row.get("compression_run_id")) for row in rows}
    if len(run_ids) != 1 or None in run_ids:
        raise ValueError("resume compression rows do not share one run ID")

    checkpoint_path = _checkpoint_path(output_path)
    checkpoints = [
        json.loads(line)
        for line in checkpoint_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ] if checkpoint_path.exists() else []
    checkpoint_by_id: dict[str, dict[str, Any]] = {}
    for checkpoint in checkpoints:
        if checkpoint.get("schema") != "ccdf.compression-cache.row-checksum.v1":
            raise ValueError("unexpected compression resume checksum schema")
        sample_id = str(checkpoint["sample_id"])
        if sample_id in checkpoint_by_id:
            raise ValueError("compression resume checksum file contains duplicate sample IDs")
        checkpoint_by_id[sample_id] = checkpoint

    for sample, row in zip(samples, rows, strict=False):
        sample_id = str(sample["sample_id"])
        if row.get("schema") != SCHEMA:
            raise ValueError("unexpected compression resume row schema")
        if row.get("original_prompt_sha256") != _sha256_text(str(sample["prompt"])):
            raise ValueError("compression resume original prompt hash mismatch")
        if row.get("status") not in {"success", "fallback", "failed"}:
            raise ValueError("compression resume row has invalid status")
        checkpoint = checkpoint_by_id.pop(sample_id, None)
        if checkpoint is None:
            _append_checkpoint(checkpoint_path, row)
        elif checkpoint["row_sha256"] != _row_sha256(row):
            raise ValueError("compression resume row checksum mismatch")
    if checkpoint_by_id:
        raise ValueError("compression resume checksum contains rows absent from cache")
    return rows


def compress_samples(
    config: Rec2Config,
    samples: list[dict[str, Any]],
    *,
    keep_rate: float | None = None,
    output_path: Path | None = None,
    resume: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compress each sample exactly once and return its reusable cache plus load audit."""
    if keep_rate is not None and not 0 < keep_rate <= 1:
        raise ValueError("compression keep_rate must be in (0, 1]")
    if not torch.cuda.is_available():
        raise ModelContractError("compressor requires CUDA; CPU fallback is forbidden")
    profile = dict(config.require("models.compressor"))
    budget_gib = _canonical_budget(config)
    requested = str(profile.get("device", "cuda:0"))
    index = _device_index(requested)
    if index >= torch.cuda.device_count():
        raise ModelContractError(f"compressor CUDA device index {index} is unavailable")
    torch.cuda.set_device(index)
    path = Path(profile["local_path"]).resolve()
    if not path.is_dir():
        raise FileNotFoundError(f"compressor model path not found: {path}")

    from llmlingua import PromptCompressor

    compressor = None
    existing_rows: list[dict[str, Any]] = []
    if output_path is not None and resume:
        existing_rows = _load_resume_rows(output_path, samples)
    elif output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("", encoding="utf-8")
        _checkpoint_path(output_path).write_text("", encoding="utf-8")
    reset_peak_memory()
    load_started = time.perf_counter()
    try:
        compressor = PromptCompressor(
            model_name=str(path),
            device_map=requested,
            model_config={"local_files_only": True, "trust_remote_code": True},
            use_llmlingua2=True,
        )
        compressor_batch_size = int(profile.get("max_batch_size", 1))
        if compressor_batch_size < 1:
            raise ModelContractError("compressor max_batch_size must be positive")
        compressor.max_batch_size = compressor_batch_size
        from transformers import AutoTokenizer

        target_tokenizer = AutoTokenizer.from_pretrained(
            str(config.require("models.baseline.tokenizer_path")),
            local_files_only=True,
            trust_remote_code=bool(config.get("models.baseline.trust_remote_code", True)),
        )
        synchronize(index)
        load_latency_ms = (time.perf_counter() - load_started) * 1000.0
        resolved, dtypes = _placement(compressor.model, expected_index=index)
        load_memory = collect_memory(
            limit_gib=budget_gib
        )
        if load_memory.gate_pass is False:
            raise ModelContractError(
                "compressor peak reserved memory exceeded its configured budget: "
                f"{load_memory.peak_reserved_bytes / 1024**3:.3f} GiB"
            )
        identity = {
            "model_id": str(profile["model_id"]),
            "local_path": str(path),
            "config_sha256": _sha256_file(path / "config.json"),
        }
        device = {
            "requested": requested,
            "resolved": resolved,
            "cuda_device_index": index,
            "cuda_device_name": torch.cuda.get_device_name(index),
        }
        compression_run_id = (
            str(existing_rows[0]["compression_run_id"])
            if existing_rows
            else f"compression-{uuid.uuid4()}"
        )
        rows: list[dict[str, Any]] = list(existing_rows)
        for sample in samples[len(existing_rows):]:
            original = str(sample["prompt"])
            safeguarded = None
            validation = None
            original_target_tokens = _token_count(target_tokenizer, original)
            selected_rate = keep_rate if keep_rate is not None else adaptive_keep_rate(
                config, original_target_tokens
            )
            retry_rate = float(
                config.require("dataset_smoke.compression.adaptive_keep_rate.retry_keep_rate")
            )
            attempted_rates: list[float] = []
            attempts: list[dict[str, Any]] = []
            compression_text = (
                str(sample["context"])
                if sample.get("dataset") == "qmsum" and sample.get("context")
                else original
            )
            base = {
                    "schema": SCHEMA,
                    "compression_run_id": compression_run_id,
                    "dataset": str(sample["dataset"]),
                    "split": str(sample["split"]),
                    "sample_id": str(sample["sample_id"]),
                    "original_prompt": original,
                    "original_prompt_sha256": _sha256_text(original),
                    "target_user_original_tokens": original_target_tokens,
                    "requested_keep_rate": selected_rate,
                    "compressor_device": device,
                    "compressor_dtype": dtypes,
                    "compressor_model": identity,
            }
            reset_peak_memory()
            synchronize(index)
            started = time.perf_counter()
            try:
                rates = [selected_rate]
                if retry_rate != selected_rate:
                    rates.append(retry_rate)
                def compress_at_rate(texts: list[str], rate: float) -> list[str]:
                    with torch.inference_mode():
                        result = compressor.compress_prompt_llmlingua2(
                            texts,
                            rate=rate,
                            use_context_level_filter=False,
                            use_token_level_filter=True,
                        )
                    return [str(value) for value in result["compressed_prompt_list"]]

                final_safeguarded, attempts = run_safeguarded_attempts(
                    compression_text, rates, compress_at_rate
                )
                attempted_rates.extend(float(row["keep_rate"]) for row in attempts)
                safeguarded = final_safeguarded
                validation = (
                    final_safeguarded.validation.to_dict()
                    if final_safeguarded is not None
                    else {"passed": False, "checks": {}, "failure_reasons": attempts[-1]["failure_reasons"], "diagnostic_failures": []}
                )
                synchronize(index)
                latency_ms = (time.perf_counter() - started) * 1000.0
                memory = collect_memory(limit_gib=budget_gib)
                if memory.gate_pass is False:
                    raise ModelContractError(
                        f"compressor memory gate failed for sample {sample['sample_id']}"
                    )
                if final_safeguarded is None:
                    compressed = original
                    compressed_context = str(sample.get("context", "")) if sample.get("dataset") == "qmsum" else None
                    origin_tokens = _token_count(compressor.tokenizer, compression_text)
                    compressed_tokens = origin_tokens
                    final_target_tokens = original_target_tokens
                    row_status = "fallback"
                    compression_status = "FACT_SAFETY_FALLBACK"
                    compression_applied = False
                    fallback_reason = "fact validation failed after adaptive retry"
                else:
                    safeguarded = final_safeguarded
                    compressed_context = (
                        safeguarded.reconstructed_prompt if sample.get("dataset") == "qmsum" else None
                    )
                    if compressed_context is not None:
                        if original.count(compression_text) != 1:
                            raise ValueError("QMSum selected context is not unique in rendered prompt")
                        compressed = original.replace(compression_text, compressed_context, 1)
                    else:
                        compressed = safeguarded.reconstructed_prompt
                    origin_tokens = _token_count(compressor.tokenizer, compression_text)
                    compressed_tokens = _token_count(
                        compressor.tokenizer,
                        compressed_context if compressed_context is not None else compressed,
                    )
                    final_target_tokens = _token_count(target_tokenizer, compressed)
                    row_status = "success"
                    compression_status = "COMPRESSED"
                    compression_applied = True
                    fallback_reason = None
                validation["checks"]["compressor_token_reduction"] = (
                    compressed_tokens < origin_tokens
                )
                if not validation["checks"]["compressor_token_reduction"]:
                    validation["diagnostic_failures"].append("compressor_token_reduction")
                selection = sample.get("metadata", {}).get("context_selection", {})
                selected_context_tokens = selection.get("selected_context_token_count")
                compressed_context_target_tokens = (
                    _token_count(target_tokenizer, compressed_context)
                    if compressed_context is not None
                    else None
                )
                row = {
                    **base,
                    "compressed_prompt": compressed,
                    "compressed_prompt_sha256": _sha256_text(compressed),
                    "compression_applied": compression_applied,
                    "compression_status": compression_status,
                    "fallback_reason": fallback_reason,
                    "attempted_keep_rates": attempted_rates,
                    "compression_attempts": attempts,
                    "protected_spans": (
                        safeguarded.protected_spans if safeguarded is not None else None
                    ),
                    "compressible_spans": (
                        safeguarded.compressible_spans if safeguarded is not None else None
                    ),
                    "compressed_spans": (
                        list(safeguarded.compressed_spans)
                        if safeguarded is not None
                        else None
                    ),
                    "safeguard_validation": validation,
                    "compressor_original_tokens": origin_tokens,
                    "compressor_compressed_tokens": compressed_tokens,
                    "compressor_token_keep_rate": compressed_tokens / origin_tokens,
                    "target_user_compressed_tokens": final_target_tokens,
                    "target_user_keep_rate": final_target_tokens / original_target_tokens,
                    "selected_context_sha256": selection.get("selected_context_sha256"),
                    "compressed_context_sha256": (
                        _sha256_text(compressed_context) if compressed_context is not None else None
                    ),
                    "selected_context_target_tokens": selected_context_tokens,
                    "compressed_context_target_tokens": compressed_context_target_tokens,
                    "selection_keep_rate": selection.get("selection_keep_rate"),
                    "llmlingua_keep_rate": (
                        compressed_context_target_tokens / selected_context_tokens
                        if compressed_context_target_tokens is not None and selected_context_tokens
                        else None
                    ),
                    "overall_keep_rate": (
                        compressed_context_target_tokens / selection["full_transcript_token_count"]
                        if compressed_context_target_tokens is not None
                        and selection.get("full_transcript_token_count")
                        else None
                    ),
                    "compressor_latency_ms": latency_ms,
                    "compressor_peak_allocated_bytes": memory.peak_allocated_bytes,
                    "compressor_peak_reserved_bytes": memory.peak_reserved_bytes,
                    "status": row_status,
                    "failure_stage": None,
                    "failure_type": None,
                    "failure_message": None,
                }
            except Exception as exc:
                synchronize(index)
                latency_ms = (time.perf_counter() - started) * 1000.0
                memory = collect_memory(limit_gib=budget_gib)
                row = {
                    **base,
                    "compressed_prompt": None,
                    "compressed_prompt_sha256": None,
                    "protected_spans": (
                        safeguarded.protected_spans if safeguarded is not None else None
                    ),
                    "compressible_spans": (
                        safeguarded.compressible_spans if safeguarded is not None else None
                    ),
                    "compressed_spans": (
                        list(safeguarded.compressed_spans) if safeguarded is not None else None
                    ),
                    "safeguard_validation": validation,
                    "compression_applied": False,
                    "compression_status": "FAILED",
                    "fallback_reason": None,
                    "attempted_keep_rates": attempted_rates,
                    "compression_attempts": attempts,
                    "compressor_original_tokens": None,
                    "compressor_compressed_tokens": None,
                    "compressor_token_keep_rate": None,
                    "target_user_compressed_tokens": None,
                    "target_user_keep_rate": None,
                    "selected_context_sha256": sample.get("metadata", {}).get("context_selection", {}).get("selected_context_sha256"),
                    "compressed_context_sha256": None,
                    "selected_context_target_tokens": sample.get("metadata", {}).get("context_selection", {}).get("selected_context_token_count"),
                    "compressed_context_target_tokens": None,
                    "selection_keep_rate": sample.get("metadata", {}).get("context_selection", {}).get("selection_keep_rate"),
                    "llmlingua_keep_rate": None,
                    "overall_keep_rate": None,
                    "compressor_latency_ms": latency_ms,
                    "compressor_peak_allocated_bytes": memory.peak_allocated_bytes,
                    "compressor_peak_reserved_bytes": memory.peak_reserved_bytes,
                    "status": "failed",
                    "failure_stage": "compression",
                    "failure_type": type(exc).__name__,
                    "failure_message": str(exc),
                }
            rows.append(row)
            if output_path is not None:
                append_jsonl(output_path, row)
                _append_checkpoint(_checkpoint_path(output_path), row)
        counts = compression_success_counts(rows)
        audit = {
            "schema": "ccdf.compressor-audit.v1",
            "compression_run_id": compression_run_id,
            "sample_count": len(rows),
            "requested_device": requested,
            "resolved_device": resolved,
            "cuda_device_index": index,
            "cuda_device_name": torch.cuda.get_device_name(index),
            "compressor_dtype": dtypes,
            "compressor_model": identity,
            "compressor_max_batch_size": compressor_batch_size,
            "model_load_latency_ms": load_latency_ms,
            "model_load_peak_allocated_bytes": load_memory.peak_allocated_bytes,
            "model_load_peak_reserved_bytes": load_memory.peak_reserved_bytes,
            "memory_gate_pass": load_memory.gate_pass,
            "silent_cpu_fallback": False,
            "canonical_reserved_budget_gib": budget_gib,
            **counts,
            "successful_samples": counts["successful_compressions"],
            "fallback_rate": counts["fallback_samples"] / len(rows) if rows else 0.0,
            "usable_samples": sum(row["status"] in {"success", "fallback"} for row in rows),
            "resumed_samples": len(existing_rows),
            "new_samples": len(rows) - len(existing_rows),
            "status": "success" if counts["failed_samples"] == 0 else "failed",
            "error": None if counts["failed_samples"] == 0 else "sample compression failure",
        }
        return rows, audit
    finally:
        _close(compressor)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
