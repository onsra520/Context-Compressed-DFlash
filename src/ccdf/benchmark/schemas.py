"""Benchmark row and condition schemas for Rec-T02B."""

from __future__ import annotations

from typing import Any

BENCHMARK_SCHEMA_VERSION = "rec-t02b.benchmark-row.v1"
CONDITION_CONTRACT_VERSION = "rec-t02b.condition.v1"

CONDITION_FIELDS = [
    "condition_id",
    "target_model_lock_id",
    "draft_model_lock_id",
    "compressor_model_lock_id",
    "tokenizer_source",
    "generation_mode",
    "max_new_tokens",
    "temperature",
    "block_size",
    "enable_thinking",
    "stop_token_ids",
    "attention_backend",
    "quantization_mode",
    "dataset_manifest_hash",
    "prompt_policy_id",
]

ROW_REQUIRED_FIELDS = [
    "run_id",
    "task_id",
    "dataset",
    "dataset_manifest_hash",
    "fixture_id",
    "fixture_content_hash",
    "condition",
    "source_commit",
    "resolved_config_hash",
    "prompt_policy_id",
    "structured_prompt_parts_hash",
    "precompression_prompt_hash",
    "final_prompt_hash",
    "input_tokens_precompression",
    "input_tokens_final",
    "generated_text",
    "reference_answer",
    "generated_text_hash",
    "output_token_ids_hash",
    "output_tokens",
    "stop_reason",
    "cap_hit",
    "success",
    "error",
    "model_init_ms",
    "compressor_init_ms",
    "compression_total_ms",
    "target_prefill_ms",
    "draft_prefill_ms",
    "decode_total_ms",
    "request_e2e_ms",
    "peak_allocated_bytes",
    "peak_reserved_bytes",
    "measurement_scope",
    "measurement_mode",
    "verification_calls",
    "acceptance_lengths",
    "tau_tokens_advanced_per_verification",
    "draft_tokens_proposed",
    "accepted_draft_tokens",
    "draft_acceptance_rate",
    "rollback_tokens",
    "quality",
]

PROFILING_ONLY_FIELDS = {
    "draft_proposal_ms",
    "target_verification_ms",
    "cache_management_ms",
    "synchronization_overhead_ms",
}


def benchmark_schema() -> dict[str, Any]:
    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "required_fields": ROW_REQUIRED_FIELDS,
        "profiling_only_fields": sorted(PROFILING_ONLY_FIELDS),
        "condition_fields": CONDITION_FIELDS,
        "layers": ["execution", "measurement", "evaluation", "aggregation"],
    }


def condition_contract() -> dict[str, Any]:
    return {
        "contract_version": CONDITION_CONTRACT_VERSION,
        "required_fields": CONDITION_FIELDS,
        "field_scope": {
            "tokenizer_source": "resolved condition config only",
            "dataset_manifest_hash": "dataset identity; aggregation must match exactly",
            "prompt_policy_id": "prompt renderer/evaluator identity",
        },
    }


def validate_condition(condition: dict[str, Any]) -> None:
    missing = [field for field in CONDITION_FIELDS if field not in condition]
    if missing:
        raise ValueError(f"condition missing required fields: {missing}")
    if not condition["condition_id"]:
        raise ValueError("condition_id is required")


def validate_row(row: dict[str, Any]) -> None:
    missing = [field for field in ROW_REQUIRED_FIELDS if field not in row]
    if missing:
        raise ValueError(f"row missing required fields: {missing}")
    validate_condition(row["condition"])
    mode = row["measurement_mode"]
    if mode not in {"benchmark", "profiling", "smoke"}:
        raise ValueError(f"invalid measurement_mode: {mode}")
    profiling_present = PROFILING_ONLY_FIELDS.intersection(row)
    if mode in {"benchmark", "smoke"} and profiling_present:
        raise ValueError(
            f"profiling fields present in {mode} mode: "
            f"{sorted(profiling_present)}"
        )
    if row["condition"]["tokenizer_source"] != row["quality"]["tokenizer_source"]:
        raise ValueError("tokenizer scope mixed between condition and evaluator")
    if row["dataset_manifest_hash"] != row["condition"]["dataset_manifest_hash"]:
        raise ValueError("dataset manifest hash mismatch between identity and condition")
