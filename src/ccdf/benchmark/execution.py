"""Synthetic execution for contract validation."""

from __future__ import annotations

from typing import Any

from ccdf.datasets.hashing import hash_json, hash_text
from ccdf.evaluation import gsm8k, qmsum


def resolved_condition(condition_id: str, dataset_manifest_hash: str) -> dict[str, Any]:
    is_dflash = condition_id == "dflash-r1"
    return {
        "condition_id": condition_id,
        "target_model_lock_id": "target:qwen3-4b-bnb-4bit@cad0bed",
        "draft_model_lock_id": "drafter:qwen3-4b-dflash-b16@b74e3a" if is_dflash else None,
        "compressor_model_lock_id": None,
        "tokenizer_source": "target",
        "generation_mode": "dflash" if is_dflash else "autoregressive",
        "max_new_tokens": 64,
        "temperature": 0,
        "block_size": 16 if is_dflash else None,
        "enable_thinking": False,
        "stop_token_ids": [151645],
        "attention_backend": "synthetic-no-kernel",
        "quantization_mode": "nf4-bfloat16-target-lock",
        "dataset_manifest_hash": dataset_manifest_hash,
        "prompt_policy_id": "rec-t02b.synthetic-prompt.v1",
    }


def synthetic_row(
    *,
    run_id: str,
    dataset: str,
    fixture_id: str,
    fixture_content_hash: str,
    reference_answer: str,
    condition_id: str,
    dataset_manifest_hash: str,
    measurement_mode: str = "benchmark",
) -> dict[str, Any]:
    condition = resolved_condition(condition_id, dataset_manifest_hash)
    if dataset == "gsm8k":
        generated = f"Final answer: {reference_answer}"
        quality = gsm8k.evaluate(generated, reference_answer)
    else:
        generated = reference_answer[:160]
        quality = qmsum.evaluate(generated, reference_answer)
    is_dflash = condition_id == "dflash-r1"
    acceptance_lengths = [4, 3, 5] if is_dflash else []
    verification_calls = len(acceptance_lengths)
    tokens_advanced = sum(acceptance_lengths)
    accepted_draft_tokens = tokens_advanced - verification_calls if is_dflash else 0
    draft_tokens_proposed = accepted_draft_tokens + (2 if is_dflash else 0)
    row = {
        "run_id": run_id,
        "task_id": "Rec-T02B",
        "dataset": dataset,
        "dataset_manifest_hash": dataset_manifest_hash,
        "fixture_id": fixture_id,
        "fixture_content_hash": fixture_content_hash,
        "condition": condition,
        "source_commit": "synthetic-rec-t02b",
        "resolved_config_hash": hash_json(condition),
        "prompt_policy_id": condition["prompt_policy_id"],
        "structured_prompt_parts_hash": hash_text(f"{dataset}:{fixture_id}:parts"),
        "precompression_prompt_hash": hash_text(f"{dataset}:{fixture_id}:pre"),
        "final_prompt_hash": hash_text(f"{dataset}:{fixture_id}:final"),
        "input_tokens_precompression": 32 if dataset == "gsm8k" else 512,
        "input_tokens_final": 32 if dataset == "gsm8k" else 512,
        "generated_text": generated,
        "generated_text_hash": hash_text(generated),
        "output_token_ids_hash": hash_text("synthetic-token-ids:" + generated),
        "output_tokens": 6 if dataset == "gsm8k" else 34,
        "stop_reason": "eos",
        "cap_hit": False,
        "success": True,
        "error": None,
        "model_init_ms": 100.0,
        "compressor_init_ms": 0.0,
        "compression_total_ms": 0.0,
        "target_prefill_ms": 20.0 if dataset == "gsm8k" else 90.0,
        "draft_prefill_ms": 8.0 if is_dflash else 0.0,
        "decode_total_ms": 30.0 if is_dflash else 45.0,
        "request_e2e_ms": 150.0 if is_dflash else 165.0,
        "peak_allocated_bytes": 1_000_000,
        "peak_reserved_bytes": 2_000_000,
        "measurement_scope": "process",
        "measurement_mode": measurement_mode,
        "verification_calls": verification_calls,
        "acceptance_lengths": acceptance_lengths,
        "tau_tokens_advanced_per_verification": tokens_advanced / verification_calls
        if verification_calls
        else 0.0,
        "draft_tokens_proposed": draft_tokens_proposed,
        "accepted_draft_tokens": accepted_draft_tokens,
        "draft_acceptance_rate": accepted_draft_tokens / draft_tokens_proposed
        if draft_tokens_proposed
        else 0.0,
        "rollback_tokens": draft_tokens_proposed - accepted_draft_tokens,
        "quality": quality,
    }
    if measurement_mode == "profiling":
        row.update(
            {
                "draft_proposal_ms": 1.0,
                "target_verification_ms": 2.0,
                "cache_management_ms": 0.5,
                "synchronization_overhead_ms": 0.25,
            }
        )
    return row
