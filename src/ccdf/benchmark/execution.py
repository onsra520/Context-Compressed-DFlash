"""Explicit synthetic-only benchmark helper retained for Rec-T02B contract tests."""

from __future__ import annotations

from typing import Any

from ccdf.datasets.hashing import hash_json, hash_text
from ccdf.evaluation import gsm8k, qmsum


def resolved_condition(condition_id: str, dataset_manifest_hash: str) -> dict[str, Any]:
    is_dflash = condition_id in {"dflash-r1", "cc-dflash-r2"}
    is_cc = condition_id == "cc-dflash-r2"
    return {
        "condition_id": condition_id,
        "target_model_lock_id": "target:qwen3-4b-bnb-4bit@cad0bed",
        "draft_model_lock_id": "drafter:qwen3-4b-dflash-b16@b74e3a" if is_dflash else None,
        "compressor_model_lock_id": "llmlingua2:meetingbank-local" if is_cc else None,
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
    generated = f"Final answer: {reference_answer}" if dataset == "gsm8k" else reference_answer[:160]
    is_dflash = condition_id in {"dflash-r1", "cc-dflash-r2"}
    request = {
        "generated_text": generated,
        "output_tokens": max(1, len(generated.split())),
        "stop_reason": "eos", "cap_hit": False, "success": True, "error": None,
        "timing": {"model_init_ms": 0.0, "compressor_init_ms": 0.0, "compression_total_ms": 0.0, "target_prefill_ms": 0.0, "draft_prefill_ms": 0.0, "decode_total_ms": 0.0, "request_e2e_ms": 0.0},
        "vram": {"peak_allocated_bytes": 0, "peak_reserved_bytes": 0, "measurement_scope": "synthetic"},
        "dflash": {"verification_calls": 3 if is_dflash else 0, "acceptance_lengths": [4, 3, 5] if is_dflash else [], "draft_tokens_proposed": 11 if is_dflash else 0},
        "quality": gsm8k.evaluate(generated, reference_answer) if dataset == "gsm8k" else qmsum.evaluate(generated, reference_answer),
        "measurement_mode": measurement_mode,
    }
    timing = request["timing"]
    vram = request["vram"]
    dflash = request["dflash"]
    acceptance_lengths = dflash["acceptance_lengths"]
    verification_calls = len(acceptance_lengths)
    tokens_advanced = sum(acceptance_lengths)
    accepted_draft_tokens = tokens_advanced - verification_calls if verification_calls else 0
    draft_tokens_proposed = dflash["draft_tokens_proposed"]
    row = {
        "run_id": run_id,
        "task_id": "Rec-T02B",
        "dataset": dataset,
        "dataset_manifest_hash": dataset_manifest_hash,
        "fixture_id": fixture_id,
        "reference_answer": reference_answer,
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
        "generated_text": request["generated_text"],
        "generated_text_hash": hash_text(request["generated_text"]),
        "output_token_ids_hash": hash_text("synthetic-token-ids:" + request["generated_text"]),
        "output_tokens": request["output_tokens"],
        "stop_reason": request["stop_reason"],
        "cap_hit": request["cap_hit"],
        "success": request["success"],
        "error": request["error"],
        "model_init_ms": timing["model_init_ms"],
        "compressor_init_ms": timing["compressor_init_ms"],
        "compression_total_ms": timing["compression_total_ms"],
        "target_prefill_ms": timing["target_prefill_ms"],
        "draft_prefill_ms": timing["draft_prefill_ms"],
        "decode_total_ms": timing["decode_total_ms"],
        "request_e2e_ms": timing["request_e2e_ms"],
        "peak_allocated_bytes": vram["peak_allocated_bytes"],
        "peak_reserved_bytes": vram["peak_reserved_bytes"],
        "measurement_scope": vram["measurement_scope"],
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
        "quality": request["quality"],
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
