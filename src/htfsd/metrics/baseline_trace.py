"""Target-model-only baseline trace helpers."""

from __future__ import annotations

import time
from typing import Any

from htfsd.metrics.generation_settings import GenerationSettings, build_generation_settings
from htfsd.metrics.prompt_sets import DEFAULT_TRACE_PROMPT_SET
from htfsd.metrics.run_trace import _short_hash, _summarize_text
from htfsd.types import HTFSDConfig


def run_target_baseline_trace(
    *,
    prompts: list[str] | tuple[str, ...],
    config: HTFSDConfig,
    diagnostics: dict[str, Any],
    gemma_backend,
    generation_settings: GenerationSettings | None = None,
) -> list[dict[str, Any]]:
    """Run Gemma E2B directly over prompts and record compact metadata."""

    settings = generation_settings or build_generation_settings(config)
    gemma_model = config.models["gemma_e2b"]
    gemma_diagnostics = diagnostics.get("models", {}).get("gemma_e2b", {})
    records: list[dict[str, Any]] = []

    for index, prompt in enumerate(prompts, start=1):
        start = time.perf_counter()
        result = _generate_with_prompt_mode(
            gemma_backend,
            prompt,
            prompt_mode=settings.prompt_mode,
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
            stop=settings.stop,
        )
        elapsed = time.perf_counter() - start
        record = {
            "prompt_id": f"baseline-{index:03d}",
            "prompt_hash": _short_hash(prompt),
            "prompt_summary": _summarize_text(prompt, settings.output_summary_max_chars),
            "prompt_set_id": DEFAULT_TRACE_PROMPT_SET.prompt_set_id,
            "gemma_model_file": str(gemma_model.discovered_model_file) if gemma_model.discovered_model_file else None,
            "gemma_expected_device": gemma_model.expected_device,
            "gemma_device_status": gemma_diagnostics.get("device_status"),
            "gemma_n_gpu_layers": gemma_model.n_gpu_layers,
            "latency_seconds": elapsed,
            "gemma_decode_tokens_per_second": _tokens_per_second(result.completion_tokens, elapsed),
            "gemma_output_summary": _summarize_text(result.text, settings.output_summary_max_chars),
            "trace_kind": "target_baseline",
            "generation_settings": settings.to_metadata(),
            "capture_raw_output": settings.capture_raw_output,
        }
        if settings.capture_raw_output:
            record.update(
                {
                    "raw_prompt": prompt,
                    "baseline_raw_output": result.text,
                }
            )
        records.append(record)
    return records


def _tokens_per_second(tokens: int | None, elapsed: float) -> float | None:
    if tokens is None or elapsed <= 0:
        return None
    return tokens / elapsed


def _generate_with_prompt_mode(
    backend,
    prompt: str,
    *,
    prompt_mode: str,
    max_tokens: int,
    temperature: float,
    stop,
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
