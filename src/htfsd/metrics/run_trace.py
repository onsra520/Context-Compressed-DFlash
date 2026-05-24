"""JSON-friendly trace helpers for smoke runs."""

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
class PairSmokeTrace:
    """One low-tier pair smoke trace."""

    bridge_status: str
    rejection_reason: str | None
    fallback_count: int
    latency_seconds: float
    qwen_decode_tokens_per_second: float | None
    gemma_decode_tokens_per_second: float | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly dictionary."""

        return asdict(self)


def run_controlled_low_tier_trace(
    *,
    prompts: list[str] | tuple[str, ...],
    config: HTFSDConfig,
    diagnostics: dict[str, Any],
    qwen_backend,
    gemma_backend,
    generation_settings: GenerationSettings | None = None,
) -> list[dict[str, Any]]:
    """Run the existing pair smoke path over a fixed prompt set."""

    settings = generation_settings or build_generation_settings(config)
    qwen_model = config.models["qwen_drafter"]
    gemma_model = config.models["gemma_e2b"]
    qwen_diagnostics = diagnostics.get("models", {}).get("qwen_drafter", {})
    gemma_diagnostics = diagnostics.get("models", {}).get("gemma_e2b", {})
    records: list[dict[str, Any]] = []

    for index, prompt in enumerate(prompts, start=1):
        result = run_pair_smoke(
            prompt=prompt,
            qwen_backend=qwen_backend,
            gemma_backend=gemma_backend,
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
            stop=settings.stop,
        )
        record = _base_low_tier_record(
            prompt_id=f"trace-{index:03d}",
            prompt=prompt,
            result=result,
            qwen_model=qwen_model,
            gemma_model=gemma_model,
            qwen_diagnostics=qwen_diagnostics,
            gemma_diagnostics=gemma_diagnostics,
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
    qwen_model = config.models["qwen_drafter"]
    gemma_model = config.models["gemma_e2b"]
    qwen_diagnostics = diagnostics.get("models", {}).get("qwen_drafter", {})
    gemma_diagnostics = diagnostics.get("models", {}).get("gemma_e2b", {})
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
        )
        fallback_used = result.fallback_count > 0
        record = _base_low_tier_record(
            prompt_id=f"controlled-{index:03d}",
            prompt=prompt,
            result=result,
            qwen_model=qwen_model,
            gemma_model=gemma_model,
            qwen_diagnostics=qwen_diagnostics,
            gemma_diagnostics=gemma_diagnostics,
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
    result,
    qwen_model,
    gemma_model,
    qwen_diagnostics: dict[str, Any],
    gemma_diagnostics: dict[str, Any],
    settings: GenerationSettings,
) -> dict[str, Any]:
    return {
        "prompt_id": prompt_id,
        "prompt_hash": _short_hash(prompt),
        "prompt_summary": _summarize_text(prompt, settings.output_summary_max_chars),
        "prompt_set_id": DEFAULT_TRACE_PROMPT_SET.prompt_set_id,
        "qwen_model_file": str(qwen_model.discovered_model_file) if qwen_model.discovered_model_file else None,
        "gemma_model_file": str(gemma_model.discovered_model_file) if gemma_model.discovered_model_file else None,
        "qwen_expected_device": qwen_model.expected_device,
        "gemma_expected_device": gemma_model.expected_device,
        "qwen_device_status": qwen_diagnostics.get("device_status"),
        "gemma_device_status": gemma_diagnostics.get("device_status"),
        "qwen_n_gpu_layers": qwen_model.n_gpu_layers,
        "gemma_n_gpu_layers": gemma_model.n_gpu_layers,
        "bridge_status": result.bridge_status,
        "rejection_reason": result.rejection_reason,
        "fallback_count": result.fallback_count,
        "draft_valid_count": result.draft_valid_count,
        "draft_rejected_count": result.draft_rejected_count,
        "latency_seconds": result.latency_seconds,
        "qwen_decode_tokens_per_second": result.qwen_decode_tokens_per_second,
        "gemma_decode_tokens_per_second": result.gemma_decode_tokens_per_second,
        "qwen_output_summary": _summarize_text(result.raw_draft_text, settings.output_summary_max_chars),
        "gemma_output_summary": _summarize_text(result.gemma_output_text, settings.output_summary_max_chars),
        "generation_settings": settings.to_metadata(),
        "capture_raw_output": settings.capture_raw_output,
    }


class _FixedDraftBackend:
    def __init__(self, text: str) -> None:
        self.text = text

    def generate_text(self, prompt: str, *, max_tokens: int, temperature: float, stop=None) -> TextGenerationResult:
        return TextGenerationResult(text=self.text, completion_tokens=None)
