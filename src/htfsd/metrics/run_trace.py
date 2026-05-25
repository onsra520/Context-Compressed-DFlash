"""JSON-friendly trace helpers for controlled low-tier runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from htfsd.metrics.generation_settings import GenerationSettings, build_generation_settings
from htfsd.metrics.prompt_sets import DEFAULT_TRACE_PROMPT_SET, default_trace_prompt_texts
from htfsd.text_bridge.pair_smoke import run_pair_smoke
from htfsd.types import TextGenerationResult
from htfsd.types import HTFSDConfig


DEFAULT_TRACE_PROMPTS = default_trace_prompt_texts()

DEFAULT_CONTROLLED_FALLBACK_CASES = (
    {
        "case_id": "valid_plain_draft",
        "prompt": "Controlled valid draft case.",
        "raw_draft": "Speculative decoding drafts tokens before verification.",
    },
    {
        "case_id": "empty_draft",
        "prompt": "Controlled empty draft case.",
        "raw_draft": "",
    },
    {
        "case_id": "unclosed_think",
        "prompt": "Controlled unclosed think case.",
        "raw_draft": "<think>I am reasoning",
    },
    {
        "case_id": "complete_think_then_empty",
        "prompt": "Controlled complete think case.",
        "raw_draft": "<think>hidden reasoning</think>",
    },
)

@dataclass(frozen=True)
class LowTierTrace:
    """One low-tier trace summary."""

    bridge_status: str
    rejection_reason: str | None
    fallback_count: int
    latency_seconds: float
    drafter_decode_tokens_per_second: float | None
    verifier_decode_tokens_per_second: float | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly dictionary."""

        return asdict(self)


def run_controlled_low_tier_trace(
    *,
    prompts: list[str] | tuple[str, ...],
    prompt_ids: list[str] | tuple[str, ...] | None = None,
    prompt_set_id: str = DEFAULT_TRACE_PROMPT_SET.prompt_set_id,
    config: HTFSDConfig,
    diagnostics: dict[str, Any],
    qwen_backend,
    gemma_backend,
    generation_settings: GenerationSettings | None = None,
) -> list[dict[str, Any]]:
    """Run the existing pair smoke path over a fixed prompt set."""

    settings = generation_settings or build_generation_settings(config)
    drafter_model = config.models["drafter"]
    verifier_model = config.models["verifier"]
    drafter_diagnostics = _role_diagnostics(diagnostics, "drafter")
    verifier_diagnostics = _role_diagnostics(diagnostics, "verifier")
    records: list[dict[str, Any]] = []

    if prompt_ids is not None and len(prompt_ids) != len(prompts):
        raise ValueError("prompt_ids must have the same length as prompts")

    for index, prompt in enumerate(prompts, start=1):
        prompt_id = prompt_ids[index - 1] if prompt_ids is not None else f"trace-{index:03d}"
        result = run_pair_smoke(
            prompt=prompt,
            qwen_backend=qwen_backend,
            gemma_backend=gemma_backend,
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
            stop=settings.stop,
            prompt_mode=settings.prompt_mode,
        )
        record = _base_low_tier_record(
            prompt_id=prompt_id,
            prompt=prompt,
            prompt_set_id=prompt_set_id,
            result=result,
            drafter_model=drafter_model,
            verifier_model=verifier_model,
            drafter_diagnostics=drafter_diagnostics,
            verifier_diagnostics=verifier_diagnostics,
            settings=settings,
        )
        if settings.capture_raw_output:
            record.update(
                {
                    "raw_prompt": prompt,
                    "qwen_raw_output": result.raw_draft_text,
                    "gemma_raw_output": result.gemma_output_text,
                }
            )
        records.append(record)
    return records


def run_controlled_fallback_trace_cases(
    *,
    cases: tuple[dict[str, str], ...],
    config: HTFSDConfig,
    diagnostics: dict[str, Any],
    gemma_backend,
    generation_settings: GenerationSettings | None = None,
) -> list[dict[str, Any]]:
    """Run controlled draft cases through the pair path with injected Qwen output."""

    settings = generation_settings or build_generation_settings(config)
    drafter_model = config.models["drafter"]
    verifier_model = config.models["verifier"]
    drafter_diagnostics = _role_diagnostics(diagnostics, "drafter")
    verifier_diagnostics = _role_diagnostics(diagnostics, "verifier")
    records: list[dict[str, Any]] = []

    for index, case in enumerate(cases, start=1):
        prompt = case["prompt"]
        qwen_backend = _FixedDraftBackend(case["raw_draft"])
        result = run_pair_smoke(
            prompt=prompt,
            qwen_backend=qwen_backend,
            gemma_backend=gemma_backend,
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
            stop=settings.stop,
            prompt_mode=settings.prompt_mode,
        )
        fallback_used = result.fallback_count > 0
        record = _base_low_tier_record(
            prompt_id=f"controlled-{index:03d}",
            prompt=prompt,
            prompt_set_id="controlled-fallback-cases",
            result=result,
            drafter_model=drafter_model,
            verifier_model=verifier_model,
            drafter_diagnostics=drafter_diagnostics,
            verifier_diagnostics=verifier_diagnostics,
            settings=settings,
        )
        record.update(
            {
                "case_id": case["case_id"],
                "controlled_qwen_draft": case["raw_draft"],
                "gemma_fallback_used": fallback_used,
            }
        )
        if settings.capture_raw_output:
            record.update(
                {
                    "raw_prompt": prompt,
                    "qwen_raw_output": result.raw_draft_text,
                    "gemma_raw_output": result.gemma_output_text,
                }
            )
        records.append(record)
    return records


def write_trace_json(
    *,
    records: list[dict[str, Any]],
    output_dir: Path,
    metadata: dict[str, Any] | None = None,
    trace_kind: str = "low-tier",
) -> Path:
    """Write a compact JSON trace report for agent inspection."""

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{trace_kind}-trace.json"
    payload = {
        "metadata": metadata or {},
        "records": records,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _summarize_text(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


def _base_low_tier_record(
    *,
    prompt_id: str,
    prompt: str,
    prompt_set_id: str,
    result,
    drafter_model,
    verifier_model,
    drafter_diagnostics: dict[str, Any],
    verifier_diagnostics: dict[str, Any],
    settings: GenerationSettings,
) -> dict[str, Any]:
    record = {
        "prompt_id": prompt_id,
        "prompt_hash": _short_hash(prompt),
        "prompt_summary": _summarize_text(prompt, settings.output_summary_max_chars),
        "prompt_set_id": prompt_set_id,
        "drafter_model_file": str(drafter_model.discovered_model_file)
        if drafter_model.discovered_model_file
        else None,
        "verifier_model_file": str(verifier_model.discovered_model_file)
        if verifier_model.discovered_model_file
        else None,
        "drafter_expected_device": drafter_model.expected_device,
        "verifier_expected_device": verifier_model.expected_device,
        "drafter_device_status": drafter_diagnostics.get("device_status"),
        "verifier_device_status": verifier_diagnostics.get("device_status"),
        "drafter_n_gpu_layers": drafter_model.n_gpu_layers,
        "verifier_n_gpu_layers": verifier_model.n_gpu_layers,
        "bridge_status": result.bridge_status,
        "rejection_reason": result.rejection_reason,
        "fallback_count": result.fallback_count,
        "draft_valid_count": result.draft_valid_count,
        "draft_rejected_count": result.draft_rejected_count,
        "latency_seconds": result.latency_seconds,
        "drafter_decode_tokens_per_second": result.drafter_decode_tokens_per_second,
        "verifier_decode_tokens_per_second": result.verifier_decode_tokens_per_second,
        "qwen_output_summary": _summarize_text(result.raw_draft_text, settings.output_summary_max_chars),
        "gemma_output_summary": _summarize_text(result.gemma_output_text, settings.output_summary_max_chars),
        "generation_settings": settings.to_metadata(),
        "capture_raw_output": settings.capture_raw_output,
    }
    record.update(_low_tier_compatibility_aliases(record))
    return record


def _role_diagnostics(diagnostics: dict[str, Any], role: str) -> dict[str, Any]:
    models = diagnostics.get("models", {})
    if role in models:
        return models[role]
    aliases = {
        "drafter": "qwen_drafter",
        "verifier": "gemma_e2b",
        "target": "gemma_e4b",
    }
    return models.get(aliases.get(role, role), {})


def _low_tier_compatibility_aliases(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "qwen_model_file": record["drafter_model_file"],
        "gemma_model_file": record["verifier_model_file"],
        "qwen_expected_device": record["drafter_expected_device"],
        "gemma_expected_device": record["verifier_expected_device"],
        "qwen_device_status": record["drafter_device_status"],
        "gemma_device_status": record["verifier_device_status"],
        "qwen_n_gpu_layers": record["drafter_n_gpu_layers"],
        "gemma_n_gpu_layers": record["verifier_n_gpu_layers"],
        "qwen_decode_tokens_per_second": record["drafter_decode_tokens_per_second"],
        "gemma_decode_tokens_per_second": record["verifier_decode_tokens_per_second"],
    }


class _FixedDraftBackend:
    def __init__(self, text: str) -> None:
        self.text = text

    def generate_text(self, prompt: str, *, max_tokens: int, temperature: float, stop=None) -> TextGenerationResult:
        return TextGenerationResult(text=self.text, completion_tokens=None)

    def generate_chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
        stop=None,
    ) -> TextGenerationResult:
        return TextGenerationResult(text=self.text, completion_tokens=None)
