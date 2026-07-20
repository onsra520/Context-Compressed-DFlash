"""
Metric normalizer for the CC-DFlash demo API.

Maps the raw engine result dict to a flat, display-ready payload.

Correctness rules:
- Baseline-AR / DFlash-R1:
    compression_applied = False
    compression_bypassed = False
    compression_ratio = null
    prompt_reduction_* = null
    dflash-specific fields (tau, acceptance rate, etc.) = null for baseline
- CC-DFlash question-only:
    compression_applied = False
    compression_bypassed = True  (bypass_reason = "empty_context")
    ratio/reduction = null
- CC-DFlash with context:
    real values from engine output
- Do NOT invent values; use None for unavailable metrics.
"""
from __future__ import annotations

from typing import Any

_DISPLAY_NAMES: dict[str, str] = {
    "baseline-ar": "Baseline-AR",
    "dflash-r1": "D-Flash",
    "cc-dflash-r2": "CC-DFlash (CPU)",
    "cc-dflash-r2-gpu": "CC-DFlash (GPU)",
}

_DFLASH_CONDITIONS = {"dflash-r1", "cc-dflash-r2", "cc-dflash-r2-gpu"}
_CC_CONDITIONS = {"cc-dflash-r2", "cc-dflash-r2-gpu"}


def normalize_metrics(raw: dict[str, Any]) -> dict[str, Any]:  # noqa: C901
    condition_id: str = raw.get("condition", "")
    is_dflash = condition_id in _DFLASH_CONDITIONS
    is_cc = condition_id in _CC_CONDITIONS

    timing: dict[str, Any] = raw.get("timing") or {}
    output_tokens: int = raw.get("output_tokens") or 0

    decode_total_ms: float | None = timing.get("decode_total_ms")
    warm_request_e2e_ms: float | None = timing.get("warm_request_e2e_ms")

    # Throughput derived from decode time only.
    generation_tok_s: float | None = None
    if decode_total_ms and decode_total_ms > 0 and output_tokens > 0:
        generation_tok_s = output_tokens / (decode_total_ms / 1000)

    # --- Token counts ---
    # engine["input_tokens"] == final prompt token count (after compression).
    # engine["compression"]["token_scope"]["precompression_target_prompt_tokens"]
    #   == pre-compression count.
    input_tokens_final: int | None = raw.get("input_tokens")
    compression_block: dict[str, Any] | None = raw.get("compression")
    token_scope: dict[str, Any] = (
        (compression_block or {}).get("token_scope") or {}
    )
    input_tokens_precompression: int | None = token_scope.get(
        "precompression_target_prompt_tokens"
    )
    # For non-CC conditions there is no compression block; pre == final.
    if input_tokens_precompression is None:
        input_tokens_precompression = input_tokens_final

    # --- Compression metrics ---
    compression_applied: bool = False
    compression_bypassed: bool = False
    compression_bypass_reason: str | None = None
    compression_ratio: float | None = None
    prompt_reduction_tokens: int | None = None
    prompt_reduction_pct: float | None = None

    if is_cc and compression_block is not None:
        raw_applied: bool = bool(compression_block.get("applied"))
        raw_bypassed: bool = bool(compression_block.get("bypassed"))
        compression_applied = raw_applied and not raw_bypassed
        compression_bypassed = raw_bypassed
        compression_bypass_reason = compression_block.get("bypass_reason")

        if compression_applied:
            pre = input_tokens_precompression
            final = input_tokens_final
            if pre and final and final > 0:
                compression_ratio = pre / final
            reduction_tokens_raw = token_scope.get("full_prompt_reduction_tokens")
            reduction_pct_raw = token_scope.get("full_prompt_reduction_pct")
            # Engine stores reduction_pct in token_scope; derive tokens if missing.
            if reduction_tokens_raw is not None:
                prompt_reduction_tokens = int(reduction_tokens_raw)
            elif pre is not None and final is not None:
                prompt_reduction_tokens = pre - final
            if reduction_pct_raw is not None:
                prompt_reduction_pct = float(reduction_pct_raw)
            elif pre and final is not None:
                prompt_reduction_pct = (1.0 - final / pre) * 100 if pre else 0.0

    # --- DFlash-specific metrics ---
    dflash_block: dict[str, Any] | None = raw.get("dflash")

    def _dflash(key: str) -> Any:
        if not is_dflash or dflash_block is None:
            return None
        return dflash_block.get(key)

    # --- Resource / VRAM ---
    resource_block: dict[str, Any] = raw.get("resource") or {}
    vram_block: dict[str, Any] = raw.get("vram") or {}

    peak_cuda_allocated_bytes: int | None = (
        resource_block.get("peak_cuda_allocated_bytes")
        or vram_block.get("peak_allocated_bytes")
    )
    peak_cuda_reserved_bytes: int | None = (
        resource_block.get("peak_cuda_reserved_bytes")
        or vram_block.get("peak_reserved_bytes")
    )

    return {
        # Identity
        "condition_id": condition_id,
        "display_name": _DISPLAY_NAMES.get(condition_id, condition_id),
        "status": "completed",
        # Output
        "generated_text": raw.get("generated_text") or "",
        "stop_reason": raw.get("stop_reason"),
        "output_tokens": output_tokens,
        # Token counts
        "input_tokens_precompression": input_tokens_precompression,
        "input_tokens_final": input_tokens_final,
        # Compression
        "compression_applied": compression_applied,
        "compression_bypassed": compression_bypassed,
        "compression_bypass_reason": compression_bypass_reason,
        "compression_ratio": compression_ratio,
        "prompt_reduction_tokens": prompt_reduction_tokens,
        "prompt_reduction_pct": prompt_reduction_pct,
        # Timing (None = not available, not zero)
        "compression_total_ms": timing.get("compression_total_ms"),
        "target_prefill_ms": timing.get("target_prefill_ms"),
        "draft_prefill_ms": timing.get("draft_prefill_ms"),
        "decode_total_ms": decode_total_ms,
        "generation_request_e2e_ms": timing.get("generation_request_e2e_ms"),
        "warm_request_e2e_ms": warm_request_e2e_ms,
        "cold_start_e2e_ms": timing.get("cold_start_e2e_ms"),
        # Throughput
        "generation_tok_s": generation_tok_s,
        # DFlash speculative decoding metrics (null for Baseline-AR)
        "target_forwards_per_output_token": _dflash("target_forwards_per_emitted_token"),
        "effective_tau": _dflash("effective_tau"),
        "draft_acceptance_rate": _dflash("draft_acceptance_rate"),
        "verification_calls": _dflash("target_block_verification_calls"),
        "draft_forward_calls": _dflash("draft_forward_calls"),
        "rollback_tokens": _dflash("rollback_tokens"),
        # Resource / VRAM
        "peak_cuda_allocated_bytes": peak_cuda_allocated_bytes,
        "peak_cuda_reserved_bytes": peak_cuda_reserved_bytes,
        "process_current_rss_bytes": resource_block.get("process_current_rss_bytes"),
        "resource_composition": raw.get("resource_composition"),
        "compressor_device": resource_block.get("compressor_device"),
        "compressor_cuda_verified": resource_block.get("compressor_cuda_verified"),
        # Bypass state
        "compressor_bypassed_not_loaded": resource_block.get(
            "compressor_resource_scope", ""
        ) == "compressor not loaded",
    }
