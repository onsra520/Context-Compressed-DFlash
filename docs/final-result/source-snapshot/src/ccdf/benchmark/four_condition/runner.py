"""Manifest-driven, condition-isolated four-condition execution."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from ...config import Rec2Config
from ...compression.llmlingua import adaptive_keep_rate
from ...evaluation import evaluate_dataset_output
from ...runtime.engine import RuntimeEngine
from ...validation.quality import evaluate_complete_answer
from .conditions import CONDITIONS, Condition
from .manifest import expected_key, manifest_sample_map, validate_manifest
from .schema import REQUIRED_FIELDS, SCHEMA, validate_record


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    validate_record(row)
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
        "schema": "ccdf.four-condition.row-checksum.v1",
        "key": list(expected_key(row)),
        "row_sha256": _row_sha256(row),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _load_resume_rows(
    output_path: Path,
    *,
    manifest: dict[str, Any],
    condition: Condition,
    expected_rows: list[dict[str, Any]],
    samples: dict[str, dict[str, Any]],
    compression: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if not output_path.exists() or output_path.stat().st_size == 0:
        return []
    rows = read_jsonl(output_path)
    expected_keys = [expected_key(row) for row in expected_rows]
    actual_keys = [expected_key(row) for row in rows]
    if actual_keys != expected_keys[: len(actual_keys)]:
        raise ValueError("resume rows are not a valid ordered prefix of the condition manifest")
    if len(actual_keys) != len(set(actual_keys)):
        raise ValueError("resume rows contain duplicate composite keys")

    checkpoint_path = _checkpoint_path(output_path)
    checkpoints = read_jsonl(checkpoint_path) if checkpoint_path.exists() else []
    checkpoint_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for checkpoint in checkpoints:
        if checkpoint.get("schema") != "ccdf.four-condition.row-checksum.v1":
            raise ValueError("unexpected resume checksum schema")
        key = tuple(checkpoint["key"])
        if key in checkpoint_by_key:
            raise ValueError("resume checksum file contains duplicate composite keys")
        checkpoint_by_key[key] = checkpoint

    for row in rows:
        validate_record(row)
        key = expected_key(row)
        sample_id = str(row["sample_id"])
        sample = samples[sample_id]
        cache = compression[sample_id]
        if row["manifest_sha256"] != manifest["manifest_sha256"]:
            raise ValueError("resume row manifest hash mismatch")
        if row["condition_id"] != condition.condition_id:
            raise ValueError("resume row condition mismatch")
        if row["original_prompt_sha256"] != _sha256_text(str(sample["prompt"])):
            raise ValueError("resume row original prompt hash mismatch")
        if row["compressed_prompt_sha256"] != cache["compressed_prompt_sha256"]:
            raise ValueError("resume row compressed prompt hash mismatch")
        checkpoint = checkpoint_by_key.pop(key, None)
        if checkpoint is None:
            # A crash can occur after the fsynced raw row and before its sidecar.
            # Adopt only the fully parsed and contract-valid raw row.
            _append_checkpoint(checkpoint_path, row)
        elif checkpoint["row_sha256"] != _row_sha256(row):
            raise ValueError("resume row checksum mismatch")
    if checkpoint_by_key:
        raise ValueError("resume checksum file contains keys absent from raw output")
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def prepare_mock_samples(config: Rec2Config) -> list[dict[str, Any]]:
    prompts = [str(prompt) for prompt in config.require("benchmark.prompts")]
    if len(prompts) != 10 or len(set(prompts)) != 10:
        raise ValueError("four-condition mock workload requires exactly 10 unique canonical prompts")
    return [
        {
            "schema": "ccdf.benchmark-sample.v1",
            "dataset": "canonical_mock",
            "split": "mock10",
            "sample_id": f"mock-{index + 1:02d}",
            "prompt": prompt,
            "metadata": {"prompt_index": index, "prompt_version": "canonical-rec3"},
        }
        for index, prompt in enumerate(prompts)
    ]


def _instrumented_config(config: Rec2Config, *, dflash: bool) -> Rec2Config:
    data = copy.deepcopy(config.data)
    if dflash:
        data["optimization"]["profile_components"] = True
    return Rec2Config(path=config.path, root=config.root, data=data)


def _target_user_tokens(engine: RuntimeEngine, prompt: str) -> int:
    encoded = engine.tokenizer(prompt, add_special_tokens=False)
    ids = encoded["input_ids"] if isinstance(encoded, dict) else encoded.input_ids
    if ids and isinstance(ids[0], list):
        ids = ids[0]
    return len(ids)


def _target_full_tokens(engine: RuntimeEngine, prompt: str) -> int:
    encoded = engine.encode_prompt(prompt)
    try:
        return int(encoded.shape[1])
    finally:
        del encoded


def validate_compression_cache(
    samples: list[dict[str, Any]],
    compression_rows: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    sample_ids = [str(sample["sample_id"]) for sample in samples]
    cache_ids = [str(row["sample_id"]) for row in compression_rows]
    duplicate_ids = sorted({sample_id for sample_id in cache_ids if cache_ids.count(sample_id) > 1})
    if duplicate_ids:
        raise ValueError(f"duplicate compression cache sample IDs: {duplicate_ids}")
    expected_ids = list(manifest["workload"]["sample_ids"])
    if sample_ids != expected_ids:
        raise ValueError("benchmark sample order does not match run manifest")
    if cache_ids != expected_ids:
        raise ValueError("compression cache sample order does not match run manifest")
    manifest_samples = manifest_sample_map(manifest)
    for sample, cache in zip(samples, compression_rows, strict=True):
        sample_id = str(sample["sample_id"])
        expected_hash = str(manifest_samples[sample_id]["prompt_sha256"])
        actual_hash = _sha256_text(str(sample["prompt"]))
        if actual_hash != expected_hash:
            raise ValueError(f"sample prompt hash mismatch for {sample_id}")
        if cache["original_prompt_sha256"] != expected_hash:
            raise ValueError(f"compression original prompt hash mismatch for {sample_id}")
        expected_rate = (
            float(manifest["requested_keep_rate"])
            if manifest.get("requested_keep_rate") is not None
            else adaptive_keep_rate(
                # The policy is embedded in the manifest; construct the tiny
                # lookup directly to keep validation independent of live config drift.
                Rec2Config(
                    path=Path("<manifest>"),
                    root=Path.cwd(),
                    data={"dataset_smoke": {"compression": {"adaptive_keep_rate": manifest["compression_policy"]}}},
                ),
                int(cache["target_user_original_tokens"]),
            )
        )
        if float(cache["requested_keep_rate"]) != expected_rate:
            raise ValueError(f"compression requested keep rate mismatch for {sample_id}")
        if cache.get("status", "success") not in {"success", "fallback"}:
            raise ValueError(f"compression cache is unusable for {sample_id}")
    return {str(row["sample_id"]): row for row in compression_rows}


def _empty_record() -> dict[str, Any]:
    return dict.fromkeys(REQUIRED_FIELDS)


def _identity_record(
    *,
    manifest: dict[str, Any],
    condition: Condition,
    sample: dict[str, Any],
    expected: dict[str, Any],
    compression: dict[str, Any] | None,
) -> dict[str, Any]:
    original = str(sample["prompt"])
    record = _empty_record()
    record.update(
        {
            "schema": SCHEMA,
            "run_id": str(manifest["run_id"]),
            "manifest_sha256": str(manifest["manifest_sha256"]),
            "process_id": os.getpid(),
            "dataset": str(sample["dataset"]),
            "split": str(sample["split"]),
            "sample_id": str(sample["sample_id"]),
            "task_type": sample.get("task_type"),
            "source_fingerprint": sample.get("source_fingerprint"),
            "prompt_version": sample.get("prompt_version"),
            "condition_id": condition.condition_id,
            "condition": condition.name,
            "runtime_condition": condition.runtime_condition,
            "prompt_kind": condition.prompt_kind,
            "repetition": expected["repetition"],
            "request_index": int(expected["request_index"]),
            "phase": str(expected["phase"]),
            "is_warmup": expected["phase"] == "warmup",
            "seed": int(manifest["seed"]),
            "original_prompt_sha256": _sha256_text(original),
            "compressed_prompt_sha256": compression.get("compressed_prompt_sha256") if compression else None,
            "compression_run_id": compression.get("compression_run_id") if compression else None,
        }
    )
    return record


def _failure_record(
    *,
    manifest: dict[str, Any],
    condition: Condition,
    sample: dict[str, Any],
    expected: dict[str, Any],
    compression: dict[str, Any] | None,
    stage: str,
    error: BaseException,
) -> dict[str, Any]:
    record = _identity_record(
        manifest=manifest,
        condition=condition,
        sample=sample,
        expected=expected,
        compression=compression,
    )
    record.update(
        {
            "status": "failed",
            "failure_stage": stage,
            "failure_type": type(error).__name__,
            "failure_message": str(error),
            "condition_process_peak_measured": False,
        }
    )
    validate_record(record)
    return record


def _success_record(
    *,
    manifest: dict[str, Any],
    config: Rec2Config,
    condition: Condition,
    sample: dict[str, Any],
    expected: dict[str, Any],
    compression: dict[str, Any],
    target_counts: tuple[int, int, int, int],
    result: Any,
) -> dict[str, Any]:
    compressed_condition = condition.prompt_kind == "compressed"
    user_original, user_compressed, full_original, full_compressed = target_counts
    dflash = result.dflash
    block_profiles = dflash.block_profiles if dflash is not None else []
    draft_time_ms = sum(float(row["draft_ms"]) for row in block_profiles) if dflash else None
    verify_time_ms = (
        sum(float(row["verify_and_accept_ms"]) for row in block_profiles) if dflash else None
    )
    acceptance_lengths = list(dflash.acceptance_lengths) if dflash else None
    prompt_index = int(sample.get("metadata", {}).get("prompt_index", -1))
    quality = (
        evaluate_complete_answer(
            prompt_index=prompt_index,
            text=result.text,
            stop_reason=result.stop_reason,
            output_tokens=result.output_tokens,
            max_new_tokens=int(manifest["max_new_tokens"]),
        ).to_dict()
        if sample["dataset"] == "canonical_mock" and prompt_index >= 0
        else None
    )
    dataset_evaluation = (
        evaluate_dataset_output(sample, str(result.text))
        if sample["dataset"] in {"gsm8k", "qmsum"}
        else None
    )
    input_prompt = str(compression["compressed_prompt"]) if compressed_condition else str(sample["prompt"])
    generation_e2e = float(result.timing.warm_request_ms)
    compressor_latency = float(compression["compressor_latency_ms"]) if compressed_condition else None
    pipeline_e2e = generation_e2e + (compressor_latency or 0.0)
    generated_tokens = int(result.output_tokens)
    token_sources = ["autoregressive"] * generated_tokens
    if dflash is not None:
        token_sources = ["target_prefill"]
        for block in dflash.structural_audit:
            emitted = int(block["emitted_advance"])
            accepted = min(int(block["accepted_count"]), emitted)
            token_sources.extend(["accepted_proposal"] * accepted)
            if emitted > accepted:
                token_sources.extend(
                    ["bonus" if block["all_proposals_accepted"] else "correction"]
                    * (emitted - accepted)
                )
        if len(token_sources) != generated_tokens:
            raise ValueError(
                "DFlash structural audit cannot account for every generated token source"
            )
    record = _identity_record(
        manifest=manifest,
        condition=condition,
        sample=sample,
        expected=expected,
        compression=compression,
    )
    record.update(
        {
            "original_prompt_text": str(sample["prompt"]),
            "compressed_prompt_text": str(compression["compressed_prompt"]),
            "input_prompt_text": input_prompt,
            "reference_text": sample.get("reference"),
            "input_prompt_sha256": _sha256_text(input_prompt),
            "requested_keep_rate": float(compression["requested_keep_rate"]),
            "compression_applied": bool(compression["compression_applied"]),
            "compression_status": str(compression["compression_status"]),
            "fallback_reason": compression.get("fallback_reason"),
            "attempted_keep_rates": list(compression["attempted_keep_rates"]),
            "compression_attempts": list(compression["compression_attempts"]),
            "compressor_original_tokens": int(compression["compressor_original_tokens"]),
            "compressor_compressed_tokens": int(compression["compressor_compressed_tokens"]),
            "compressor_token_keep_rate": float(compression["compressor_token_keep_rate"]),
            "target_user_original_tokens": user_original,
            "target_user_compressed_tokens": user_compressed,
            "target_user_token_reduction": user_original - user_compressed,
            "target_user_keep_rate": user_compressed / user_original,
            "target_user_compression_ratio": user_original / user_compressed,
            "target_full_original_tokens": full_original,
            "target_full_compressed_tokens": full_compressed,
            "target_full_token_reduction": full_original - full_compressed,
            "target_full_keep_rate": full_compressed / full_original,
            "target_full_compression_ratio": full_original / full_compressed,
            "compressor_latency_ms": compressor_latency,
            "compressor_device": compression["compressor_device"] if compressed_condition else None,
            "compressor_dtype": compression["compressor_dtype"] if compressed_condition else None,
            "compressor_model": compression["compressor_model"] if compressed_condition else None,
            "compressor_peak_allocated_bytes": int(compression["compressor_peak_allocated_bytes"]) if compressed_condition else None,
            "compressor_peak_reserved_bytes": int(compression["compressor_peak_reserved_bytes"]) if compressed_condition else None,
            "safeguard_validation": compression["safeguard_validation"] if compressed_condition else None,
            "selected_context_sha256": compression.get("selected_context_sha256"),
            "compressed_context_sha256": compression.get("compressed_context_sha256"),
            "selected_context_target_tokens": compression.get("selected_context_target_tokens"),
            "compressed_context_target_tokens": compression.get("compressed_context_target_tokens"),
            "selection_keep_rate": compression.get("selection_keep_rate"),
            "llmlingua_keep_rate": compression.get("llmlingua_keep_rate"),
            "overall_keep_rate": compression.get("overall_keep_rate"),
            "generated_token_ids": list(result.generated_token_ids),
            "generated_token_sources": token_sources,
            "generated_token_count": generated_tokens,
            "decoded_output": str(result.text),
            "parsed_answer": dataset_evaluation["parsed_answer"] if dataset_evaluation else None,
            "parser_status": dataset_evaluation["parser_status"] if dataset_evaluation else "not_applicable",
            "quality_score": dataset_evaluation["quality_score"] if dataset_evaluation else (
                float(quality["quality_pass"]) if quality is not None else None
            ),
            "quality_details": dataset_evaluation["details"] if dataset_evaluation else quality,
            "target_prefill_time_ms": float(result.timing.target_prefill_ms),
            "draft_time_ms": draft_time_ms,
            "verify_time_ms": verify_time_ms,
            "decode_time_ms": float(result.timing.decode_total_ms),
            "generation_time_ms": float(result.timing.generation_total_ms),
            "generation_warm_e2e_time_ms": generation_e2e,
            "pipeline_warm_e2e_time_ms": pipeline_e2e,
            "decode_tok_s": float(result.decode_tok_s),
            "generation_e2e_tok_s": generated_tokens / (generation_e2e / 1000.0),
            "pipeline_e2e_tok_s": generated_tokens / (pipeline_e2e / 1000.0),
            "draft_calls": int(dflash.draft_forward_calls) if dflash else None,
            "verification_calls": int(dflash.target_verification_calls) if dflash else None,
            "drafted_tokens": int(dflash.draft_tokens_proposed) if dflash else None,
            "accepted_tokens": int(dflash.accepted_draft_tokens) if dflash else None,
            "acceptance_rate": float(dflash.acceptance_rate) if dflash else None,
            "acceptance_lengths": acceptance_lengths,
            "mean_acceptance_length": sum(acceptance_lengths) / len(acceptance_lengths) if acceptance_lengths else None,
            "tau": float(dflash.effective_tau) if dflash else None,
            "generation_peak_allocated_bytes": int(result.memory.peak_allocated_bytes),
            "generation_peak_reserved_bytes": int(result.memory.peak_reserved_bytes),
            "condition_process_peak_measured": False,
            "condition_process_peak_allocated_bytes": None,
            "condition_process_peak_reserved_bytes": None,
            "stop_reason": str(result.stop_reason),
            "quality": quality,
            "model": result.model,
            "runtime": result.runtime,
            "status": "success",
            "failure_stage": None,
            "failure_type": None,
            "failure_message": None,
        }
    )
    validate_record(record)
    if dflash is not None and (not block_profiles or draft_time_ms <= 0 or verify_time_ms <= 0):
        raise ValueError("DFlash component timing is missing or invalid")
    return record


def run_condition(
    config: Rec2Config,
    *,
    manifest: dict[str, Any],
    condition_id: str,
    samples: list[dict[str, Any]],
    compression_rows: list[dict[str, Any]],
    output_path: Path | None = None,
    resume: bool = False,
) -> list[dict[str, Any]]:
    validate_manifest(manifest)
    if condition_id not in CONDITIONS:
        raise ValueError(f"unknown condition ID: {condition_id}")
    if config.path.read_bytes() and manifest["config_sha256"] != hashlib.sha256(config.path.read_bytes()).hexdigest():
        raise ValueError("current config hash does not match run manifest")
    condition = CONDITIONS[condition_id]
    sample_ids = [str(sample["sample_id"]) for sample in samples]
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("benchmark samples contain duplicate sample IDs")
    sample_by_id = {str(sample["sample_id"]): sample for sample in samples}
    compression_by_id = validate_compression_cache(samples, compression_rows, manifest)
    expected_rows = [
        row for row in manifest["expected_records"] if row["condition_id"] == condition_id
    ]
    rows: list[dict[str, Any]] = []
    if output_path is not None and resume:
        rows = _load_resume_rows(
            output_path,
            manifest=manifest,
            condition=condition,
            expected_rows=expected_rows,
            samples=sample_by_id,
            compression=compression_by_id,
        )
        completed = {expected_key(row) for row in rows}
        expected_rows = [row for row in expected_rows if expected_key(row) not in completed]
    elif output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("", encoding="utf-8")
        _checkpoint_path(output_path).write_text("", encoding="utf-8")

    if not expected_rows:
        return rows

    def persist(row: dict[str, Any]) -> None:
        rows.append(row)
        if output_path is not None:
            append_jsonl(output_path, row)
            _append_checkpoint(_checkpoint_path(output_path), row)

    runtime_config = _instrumented_config(config, dflash=condition.runtime_condition == "dflash")
    try:
        engine = RuntimeEngine(runtime_config, condition=condition.runtime_condition)
    except Exception as exc:
        for expected in expected_rows:
            sample = sample_by_id[expected["sample_id"]]
            persist(
                _failure_record(
                    manifest=manifest, condition=condition, sample=sample, expected=expected,
                    compression=compression_by_id.get(expected["sample_id"]), stage="engine_load", error=exc,
                )
            )
        return rows
    try:
        token_counts: dict[str, tuple[int, int, int, int]] = {}
        for sample in samples:
            compression = compression_by_id[sample["sample_id"]]
            if compression["status"] not in {"success", "fallback"}:
                continue
            original = str(sample["prompt"])
            compressed = str(compression["compressed_prompt"])
            token_counts[sample["sample_id"]] = (
                _target_user_tokens(engine, original),
                _target_user_tokens(engine, compressed),
                _target_full_tokens(engine, original),
                _target_full_tokens(engine, compressed),
            )
        for expected in expected_rows:
            sample = sample_by_id[expected["sample_id"]]
            compression = compression_by_id[expected["sample_id"]]
            if compression["status"] not in {"success", "fallback"}:
                persist(
                    _failure_record(
                        manifest=manifest, condition=condition, sample=sample, expected=expected,
                        compression=compression, stage="compression_safeguard",
                        error=RuntimeError(str(compression.get("failure_message") or "compression failed")),
                    )
                )
                continue
            try:
                prompt = str(compression["compressed_prompt"]) if condition.prompt_kind == "compressed" else str(sample["prompt"])
                result = engine.generate(
                    prompt,
                    dataset=str(sample["dataset"]),
                    max_new_tokens=int(manifest["max_new_tokens"]),
                )
                persist(
                    _success_record(
                        manifest=manifest, config=runtime_config, condition=condition,
                        sample=sample, expected=expected, compression=compression,
                        target_counts=token_counts[sample["sample_id"]], result=result,
                    )
                )
            except Exception as exc:
                persist(
                    _failure_record(
                        manifest=manifest, condition=condition, sample=sample, expected=expected,
                        compression=compression, stage="generation", error=exc,
                    )
                )
    finally:
        engine.close()
    return rows
