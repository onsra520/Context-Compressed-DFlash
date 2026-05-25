"""Minimal low-tier drafter-to-verifier trace path."""

from __future__ import annotations

import time
from typing import Sequence

from htfsd.text_bridge.normalization import normalize_qwen_draft
from htfsd.types import LowTierTraceResult


def run_pair_smoke(
    *,
    prompt: str,
    qwen_backend,
    gemma_backend,
    max_tokens: int,
    temperature: float,
    stop: Sequence[str] | None = None,
    prompt_mode: str = "raw",
) -> LowTierTraceResult:
    """Run a minimal low-tier trace flow without speculative acceptance claims."""

    start = time.perf_counter()
    qwen_start = time.perf_counter()
    qwen_result = _generate_with_prompt_mode(
        qwen_backend,
        prompt,
        prompt_mode=prompt_mode,
        max_tokens=max_tokens,
        temperature=temperature,
        stop=stop,
    )
    qwen_elapsed = time.perf_counter() - qwen_start

    bridge = normalize_qwen_draft(qwen_result.text)
    if bridge.bridge_status == "valid":
        gemma_prompt = _join_prompt_and_draft(prompt, bridge.normalized_text)
        fallback_count = 0
        draft_valid_count = 1
        draft_rejected_count = 0
    else:
        gemma_prompt = prompt
        fallback_count = 1
        draft_valid_count = 0
        draft_rejected_count = 1

    gemma_start = time.perf_counter()
    gemma_result = _generate_with_prompt_mode(
        gemma_backend,
        gemma_prompt,
        prompt_mode=prompt_mode,
        max_tokens=max_tokens,
        temperature=temperature,
        stop=stop,
    )
    gemma_elapsed = time.perf_counter() - gemma_start
    elapsed = time.perf_counter() - start

    return LowTierTraceResult(
        prompt=prompt,
        raw_draft_text=qwen_result.text,
        normalized_draft_text=bridge.normalized_text,
        gemma_output_text=gemma_result.text,
        bridge_status=bridge.bridge_status,
        rejection_reason=bridge.rejection_reason,
        fallback_count=fallback_count,
        draft_valid_count=draft_valid_count,
        draft_rejected_count=draft_rejected_count,
        latency_seconds=elapsed,
        drafter_decode_tokens_per_second=_tokens_per_second(qwen_result.completion_tokens, qwen_elapsed),
        verifier_decode_tokens_per_second=_tokens_per_second(gemma_result.completion_tokens, gemma_elapsed),
    )


def _tokens_per_second(tokens: int | None, elapsed: float) -> float | None:
    if tokens is None or elapsed <= 0:
        return None
    return tokens / elapsed


def _join_prompt_and_draft(prompt: str, draft_text: str) -> str:
    if not prompt or prompt[-1].isspace() or not draft_text:
        return f"{prompt}{draft_text}"
    return f"{prompt} {draft_text}"


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
