"""Synthetic request execution until Rec-T03A installs real model runtime."""

from __future__ import annotations

from typing import Any

from ccdf.evaluation import gsm8k, qmsum


def execute_request(
    *,
    condition_id: str,
    dataset: str,
    prompt: str,
    reference_answer: str | None,
    measurement_mode: str = "benchmark",
) -> dict[str, Any]:
    if condition_id not in {"baseline-ar", "dflash-r1", "cc-dflash-r2"}:
        raise ValueError(f"unsupported condition: {condition_id}")
    if measurement_mode not in {"benchmark", "profiling"}:
        raise ValueError(f"invalid measurement mode: {measurement_mode}")

    if reference_answer:
        generated = f"Final answer: {reference_answer}" if dataset == "gsm8k" else reference_answer[:160]
    elif "positive divisors" in prompt and "196" in prompt:
        generated = "Final answer: 9"
    else:
        generated = "Synthetic response pending Rec-T03A model runtime."

    is_dflash = condition_id in {"dflash-r1", "cc-dflash-r2"}
    is_cc = condition_id == "cc-dflash-r2"
    output_tokens = max(1, len(generated.split()))
    if dataset == "gsm8k" and reference_answer:
        quality = gsm8k.evaluate(generated, reference_answer)
    elif dataset == "qmsum" and reference_answer:
        quality = qmsum.evaluate(generated, reference_answer)
    else:
        quality = {
            "evaluator_version": "rec-t02b1.ad-hoc.v1",
            "label": "not_evaluated",
            "tokenizer_source": "target",
        }
    return {
        "generated_text": generated,
        "output_tokens": output_tokens,
        "stop_reason": "eos",
        "cap_hit": False,
        "success": True,
        "error": None,
        "timing": {
            "model_init_ms": 100.0,
            "compressor_init_ms": 20.0 if is_cc else 0.0,
            "compression_total_ms": 12.0 if is_cc else 0.0,
            "target_prefill_ms": 18.0 if dataset == "gsm8k" else 75.0,
            "draft_prefill_ms": 7.0 if is_dflash else 0.0,
            "decode_total_ms": 28.0 if is_dflash else 45.0,
            "request_e2e_ms": 145.0 if is_dflash else 165.0,
        },
        "vram": {
            "peak_allocated_bytes": 1_000_000,
            "peak_reserved_bytes": 2_000_000,
            "measurement_scope": "process",
        },
        "dflash": {
            "verification_calls": 3 if is_dflash else 0,
            "acceptance_lengths": [4, 3, 5] if is_dflash else [],
            "draft_tokens_proposed": 11 if is_dflash else 0,
        },
        "quality": quality,
        "measurement_mode": measurement_mode,
    }
