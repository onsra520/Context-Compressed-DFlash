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
    prompt_ids: list[str] | tuple[str, ...] | None = None,
    prompt_set_id: str = DEFAULT_TRACE_PROMPT_SET.prompt_set_id,
    config: HTFSDConfig,
    diagnostics: dict[str, Any],
    gemma_backend,
    generation_settings: GenerationSettings | None = None,
) -> list[dict[str, Any]]:
    """Run the verifier model directly over prompts and record compact metadata."""

    settings = generation_settings or build_generation_settings(config)
    verifier_model = config.models["verifier"]
    verifier_diagnostics = _role_diagnostics(diagnostics, "verifier")
    records: list[dict[str, Any]] = []

    if prompt_ids is not None and len(prompt_ids) != len(prompts):
        raise ValueError("prompt_ids must have the same length as prompts")

    for index, prompt in enumerate(prompts, start=1):
        prompt_id = prompt_ids[index - 1] if prompt_ids is not None else f"baseline-{index:03d}"
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
            "prompt_id": prompt_id,
            "prompt_hash": _short_hash(prompt),
            "prompt_summary": _summarize_text(prompt, settings.output_summary_max_chars),
            "prompt_set_id": prompt_set_id,
            "verifier_model_file": str(verifier_model.discovered_model_file)
            if verifier_model.discovered_model_file
            else None,
            "verifier_expected_device": verifier_model.expected_device,
            "verifier_device_status": verifier_diagnostics.get("device_status"),
            "verifier_n_gpu_layers": verifier_model.n_gpu_layers,
            "latency_seconds": elapsed,
            "verifier_decode_tokens_per_second": _tokens_per_second(result.completion_tokens, elapsed),
            "verifier_output_summary": _summarize_text(result.text, settings.output_summary_max_chars),
            "trace_kind": "target_baseline",
            "generation_settings": settings.to_metadata(),
            "capture_raw_output": settings.capture_raw_output,
        }
        record.update(_baseline_compatibility_aliases(record))
        if settings.capture_raw_output:
            record.update(
                {
                    "raw_prompt": prompt,
                    "baseline_raw_output": result.text,
                }
            )
        records.append(record)
    return records


def _role_diagnostics(diagnostics: dict[str, Any], role: str) -> dict[str, Any]:
    models = diagnostics.get("models", {})
    if role in models:
        return models[role]
    aliases = {"verifier": "gemma_e2b", "target": "gemma_e4b", "drafter": "qwen_drafter"}
    return models.get(aliases.get(role, role), {})


def _baseline_compatibility_aliases(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "gemma_model_file": record["verifier_model_file"],
        "gemma_expected_device": record["verifier_expected_device"],
        "gemma_device_status": record["verifier_device_status"],
        "gemma_n_gpu_layers": record["verifier_n_gpu_layers"],
        "gemma_decode_tokens_per_second": record["verifier_decode_tokens_per_second"],
        "gemma_output_summary": record["verifier_output_summary"],
    }


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
