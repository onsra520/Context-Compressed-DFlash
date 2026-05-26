"""Low-tier block-cycle trace flow for D-Flash shape alignment."""

from __future__ import annotations

from typing import Sequence
import time

from htfsd.metrics.cycle_trace_schema import (
    CYCLE_NON_CLAIMS,
    LowTierCycle,
    LowTierCycleTraceRecord,
    short_hash,
    summarize_text,
)
from htfsd.text_bridge.normalization import normalize_qwen_draft


def run_low_tier_cycle_trace_for_prompt(
    *,
    prompt: str,
    prompt_id: str,
    prompt_set_id: str,
    prompt_mode: str,
    drafter_backend,
    verifier_backend,
    draft_block_size: int,
    max_cycles: int,
    max_total_tokens: int | None,
    temperature: float,
    stop: Sequence[str] | None,
    capture_raw_output: bool,
    drafter_model_file: str | None,
    verifier_model_file: str | None,
    drafter_device_status: str | None,
    verifier_device_status: str | None,
) -> LowTierCycleTraceRecord:
    """Run one prompt through iterative draft-block cycle tracing."""

    current_context = prompt
    cycles: list[LowTierCycle] = []

    for cycle_id in range(1, max_cycles + 1):
        context_length_before = len(current_context)
        draft_start = time.perf_counter()
        draft_result = _generate_with_prompt_mode(
            drafter_backend,
            current_context,
            prompt_mode=prompt_mode,
            max_tokens=draft_block_size,
            temperature=temperature,
            stop=stop,
        )
        drafter_latency = time.perf_counter() - draft_start
        bridge = normalize_qwen_draft(draft_result.text)
        if bridge.bridge_status == "valid":
            verifier_prompt = _join_text(current_context, bridge.normalized_text)
            cycle_fallback_count = 0
        else:
            verifier_prompt = current_context
            cycle_fallback_count = 1

        verifier_start = time.perf_counter()
        verifier_result = _generate_with_prompt_mode(
            verifier_backend,
            verifier_prompt,
            prompt_mode=prompt_mode,
            max_tokens=draft_block_size,
            temperature=temperature,
            stop=stop,
        )
        verifier_latency = time.perf_counter() - verifier_start
        current_context = _join_text(verifier_prompt, verifier_result.text)
        cycles.append(
            LowTierCycle(
                cycle_id=cycle_id,
                draft_block_size=draft_block_size,
                draft_text_summary=summarize_text(draft_result.text),
                bridge_status=bridge.bridge_status,
                rejection_reason=bridge.rejection_reason,
                cycle_fallback_count=cycle_fallback_count,
                drafter_latency_seconds=drafter_latency,
                verifier_latency_seconds=verifier_latency,
                context_length_before=context_length_before,
                context_length_after=len(current_context),
                draft_text_chunk=draft_result.text if capture_raw_output else None,
                normalized_draft_text=bridge.normalized_text if capture_raw_output else None,
                verifier_raw_output=verifier_result.text if capture_raw_output else None,
            )
        )
        if max_total_tokens is not None and len(current_context.split()) >= max_total_tokens:
            break

    valid_count = sum(1 for cycle in cycles if cycle.bridge_status == "valid")
    rejected_count = sum(1 for cycle in cycles if cycle.bridge_status == "rejected")
    fallback_count = sum(cycle.cycle_fallback_count for cycle in cycles)
    return LowTierCycleTraceRecord(
        prompt_id=prompt_id,
        prompt_summary=summarize_text(prompt),
        prompt_hash=short_hash(prompt),
        prompt_set_id=prompt_set_id,
        prompt_mode=prompt_mode,
        capture_raw_output=capture_raw_output,
        draft_block_size=draft_block_size,
        max_cycles=max_cycles,
        max_total_tokens=max_total_tokens,
        total_cycles=len(cycles),
        bridge_valid_block_count=valid_count,
        bridge_rejected_block_count=rejected_count,
        cycle_fallback_count=fallback_count,
        runtime_policy="drafter_cpu_verifier_cuda",
        drafter_device_status=drafter_device_status,
        verifier_device_status=verifier_device_status,
        drafter_model_file=drafter_model_file,
        verifier_model_file=verifier_model_file,
        cycles=cycles,
        non_claims=list(CYCLE_NON_CLAIMS),
    )


def _join_text(left: str, right: str) -> str:
    if not left or left[-1].isspace() or not right:
        return f"{left}{right}"
    return f"{left} {right}"


def _generate_with_prompt_mode(
    backend,
    prompt: str,
    *,
    prompt_mode: str,
    max_tokens: int,
    temperature: float,
    stop: Sequence[str] | None,
):
    if prompt_mode == "chat":
        return backend.generate_chat(
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop,
        )
    return backend.generate_text(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        stop=stop,
    )
