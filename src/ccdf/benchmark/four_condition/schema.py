"""Unified success/failure raw-record schema and applicability checks."""

from __future__ import annotations

import math
from typing import Any

SCHEMA = "ccdf.four-condition.raw.v4"

IDENTITY_FIELDS = {
    "schema", "run_id", "manifest_sha256", "process_id", "dataset", "split",
    "sample_id", "condition_id", "condition", "runtime_condition", "prompt_kind",
    "task_type", "source_fingerprint", "prompt_version",
    "repetition", "request_index", "phase", "is_warmup", "seed",
    "original_prompt_sha256", "compressed_prompt_sha256", "input_prompt_sha256",
    "compression_run_id",
}

COMPRESSION_FIELDS = {
    "requested_keep_rate", "compression_applied", "compression_status", "fallback_reason",
    "attempted_keep_rates", "compression_attempts",
    "compressor_original_tokens", "compressor_compressed_tokens", "compressor_token_keep_rate",
    "target_user_original_tokens", "target_user_compressed_tokens",
    "target_user_token_reduction", "target_user_keep_rate", "target_user_compression_ratio",
    "target_full_original_tokens", "target_full_compressed_tokens",
    "target_full_token_reduction", "target_full_keep_rate", "target_full_compression_ratio",
    "compressor_latency_ms", "compressor_device", "compressor_dtype", "compressor_model",
    "compressor_peak_allocated_bytes", "compressor_peak_reserved_bytes",
    "safeguard_validation", "selected_context_sha256", "compressed_context_sha256",
    "selected_context_target_tokens", "compressed_context_target_tokens",
    "selection_keep_rate", "llmlingua_keep_rate", "overall_keep_rate",
}

GENERATION_FIELDS = {
    "original_prompt_text", "compressed_prompt_text", "input_prompt_text", "reference_text",
    "generated_token_ids", "generated_token_sources", "generated_token_count", "decoded_output",
    "parsed_answer", "parser_status", "quality_score", "quality_details",
    "target_prefill_time_ms", "draft_time_ms", "verify_time_ms", "decode_time_ms",
    "generation_time_ms", "generation_warm_e2e_time_ms", "pipeline_warm_e2e_time_ms",
    "decode_tok_s", "generation_e2e_tok_s", "pipeline_e2e_tok_s",
    "draft_calls", "verification_calls", "drafted_tokens", "accepted_tokens",
    "acceptance_rate", "acceptance_lengths", "mean_acceptance_length", "tau",
    "generation_peak_allocated_bytes", "generation_peak_reserved_bytes",
    "condition_process_peak_measured", "condition_process_peak_allocated_bytes",
    "condition_process_peak_reserved_bytes", "stop_reason", "quality", "model", "runtime",
}

FAILURE_FIELDS = {"status", "failure_stage", "failure_type", "failure_message"}
REQUIRED_FIELDS = IDENTITY_FIELDS | COMPRESSION_FIELDS | GENERATION_FIELDS | FAILURE_FIELDS

D_FLASH_ONLY = {
    "draft_time_ms", "verify_time_ms", "draft_calls", "verification_calls", "drafted_tokens",
    "accepted_tokens", "acceptance_rate", "acceptance_lengths", "mean_acceptance_length", "tau",
}

COMPRESSED_ONLY = {
    "compressor_latency_ms", "compressor_device", "compressor_dtype", "compressor_model",
    "compressor_peak_allocated_bytes", "compressor_peak_reserved_bytes", "safeguard_validation",
}


def _positive(record: dict[str, Any], fields: set[str]) -> bool:
    return all(
        isinstance(record[field], (int, float))
        and math.isfinite(float(record[field]))
        and float(record[field]) > 0
        for field in fields
    )


def validate_record(record: dict[str, Any]) -> None:
    missing = REQUIRED_FIELDS - set(record)
    extra = set(record) - REQUIRED_FIELDS
    if missing or extra:
        raise ValueError(
            f"unified record schema mismatch; missing={sorted(missing)} extra={sorted(extra)}"
        )
    if record["schema"] != SCHEMA:
        raise ValueError(f"unexpected unified record schema: {record['schema']}")
    if record["phase"] not in {"warmup", "measured"}:
        raise ValueError(f"invalid phase: {record['phase']}")
    if record["is_warmup"] != (record["phase"] == "warmup"):
        raise ValueError("is_warmup does not match phase")
    if record["status"] not in {"success", "failed"}:
        raise ValueError("record status must be success or failed")
    failure_values = [record[field] for field in ("failure_stage", "failure_type", "failure_message")]
    if record["status"] == "success" and any(value is not None for value in failure_values):
        raise ValueError("successful record must have null failure fields")
    if record["status"] == "failed" and any(not value for value in failure_values):
        raise ValueError("failed record must identify failure stage, type, and message")
    if record["status"] == "failed":
        return
    if not record["original_prompt_text"] or not record["compressed_prompt_text"] or not record["input_prompt_text"]:
        raise ValueError("successful record requires original, compressed, and input prompt text")
    if record["input_prompt_sha256"] is None:
        raise ValueError("successful record requires an input prompt hash")
    if record["dataset"] in {"gsm8k", "qmsum"}:
        if not record["reference_text"] or record["quality_score"] is None or not record["quality_details"]:
            raise ValueError("dataset record requires reference and quality evidence")
        if record["dataset"] == "gsm8k" and record["parser_status"] not in {
            "parsed", "empty_output", "missing_final_answer_line", "invalid_numeric"
        }:
            raise ValueError("GSM8K record has invalid parser status")
        if record["dataset"] == "qmsum" and record["parser_status"] != "not_applicable":
            raise ValueError("QMSum parser status must be not_applicable")
    if record["runtime_condition"] == "baseline":
        populated = sorted(key for key in D_FLASH_ONLY if record[key] is not None)
        if populated:
            raise ValueError(f"AR record has non-null DFlash fields: {populated}")
    if record["condition_id"] in {"C1", "C2"}:
        populated = sorted(key for key in COMPRESSED_ONLY if record[key] is not None)
        if populated:
            raise ValueError(f"original-input record has compressor metrics: {populated}")
        if record["pipeline_warm_e2e_time_ms"] != record["generation_warm_e2e_time_ms"]:
            raise ValueError("original-input pipeline E2E must equal generation E2E")
    else:
        expected = record["generation_warm_e2e_time_ms"] + record["compressor_latency_ms"]
        if not math.isclose(record["pipeline_warm_e2e_time_ms"], expected, rel_tol=1e-12):
            raise ValueError("compressed pipeline E2E arithmetic mismatch")
        if record["compression_applied"] and not record["safeguard_validation"]["passed"]:
            raise ValueError("successful compressed record requires passed safeguard validation")
        if not record["compression_applied"] and record["compression_status"] != "FACT_SAFETY_FALLBACK":
            raise ValueError("non-compressed usable record must identify fact-safety fallback")
    if not _positive(
        record,
        {
            "target_prefill_time_ms", "decode_time_ms", "generation_time_ms",
            "generation_warm_e2e_time_ms", "pipeline_warm_e2e_time_ms",
            "decode_tok_s", "generation_e2e_tok_s", "pipeline_e2e_tok_s",
        },
    ):
        raise ValueError("successful record has non-positive timing/throughput metric")
    if len(record["generated_token_ids"]) != len(record["generated_token_sources"]):
        raise ValueError("generated token IDs and source labels must have equal length")
    if record["condition_process_peak_measured"] is False and any(
        record[field] is not None
        for field in ("condition_process_peak_allocated_bytes", "condition_process_peak_reserved_bytes")
    ):
        raise ValueError("unmeasured condition-process peak must be null")
