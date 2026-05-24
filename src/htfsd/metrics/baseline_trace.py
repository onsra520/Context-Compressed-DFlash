"""Target-model-only baseline trace helpers."""

from __future__ import annotations

import time
from typing import Any

from htfsd.metrics.run_trace import _short_hash, _summarize_text
from htfsd.types import HTFSDConfig


def run_target_baseline_trace(
    *,
    prompts: list[str] | tuple[str, ...],
    config: HTFSDConfig,
    diagnostics: dict[str, Any],
    gemma_backend,
) -> list[dict[str, Any]]:
    """Run Gemma E2B directly over prompts and record compact metadata."""

    gemma_model = config.models["gemma_e2b"]
    gemma_diagnostics = diagnostics.get("models", {}).get("gemma_e2b", {})
    records: list[dict[str, Any]] = []

    for index, prompt in enumerate(prompts, start=1):
        start = time.perf_counter()
        result = gemma_backend.generate_text(
            prompt,
            max_tokens=config.generation.max_tokens,
            temperature=config.generation.temperature,
        )
        elapsed = time.perf_counter() - start
        records.append(
            {
                "prompt_id": f"baseline-{index:03d}",
                "prompt_hash": _short_hash(prompt),
                "prompt_summary": _summarize_text(prompt),
                "gemma_model_file": str(gemma_model.discovered_model_file) if gemma_model.discovered_model_file else None,
                "gemma_expected_device": gemma_model.expected_device,
                "gemma_device_status": gemma_diagnostics.get("device_status"),
                "gemma_n_gpu_layers": gemma_model.n_gpu_layers,
                "latency_seconds": elapsed,
                "gemma_decode_tokens_per_second": _tokens_per_second(result.completion_tokens, elapsed),
                "gemma_output_summary": _summarize_text(result.text),
                "trace_kind": "target_baseline",
            }
        )
    return records


def _tokens_per_second(tokens: int | None, elapsed: float) -> float | None:
    if tokens is None or elapsed <= 0:
        return None
    return tokens / elapsed
