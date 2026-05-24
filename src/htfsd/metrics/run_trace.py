"""JSON-friendly trace helpers for smoke runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from htfsd.text_bridge.pair_smoke import run_pair_smoke
from htfsd.types import TextGenerationResult
from htfsd.types import HTFSDConfig


DEFAULT_TRACE_PROMPTS = (
    "Explain speculative decoding in one short sentence.",
    "Write a five word greeting.",
    "List two benefits of GPU inference.",
)

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

SUMMARY_LIMIT = 120


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
) -> list[dict[str, Any]]:
    """Run the existing pair smoke path over a fixed prompt set."""

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
            max_tokens=config.generation.max_tokens,
            temperature=config.generation.temperature,
        )
        records.append(
            {
                "prompt_id": f"trace-{index:03d}",
                "prompt_hash": _short_hash(prompt),
                "prompt_summary": _summarize_text(prompt),
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
                "qwen_output_summary": _summarize_text(result.raw_draft_text),
                "gemma_output_summary": _summarize_text(result.gemma_output_text),
            }
        )
    return records


def run_controlled_fallback_trace_cases(
    *,
    cases: tuple[dict[str, str], ...],
    config: HTFSDConfig,
    diagnostics: dict[str, Any],
    gemma_backend,
) -> list[dict[str, Any]]:
    """Run controlled draft cases through the pair path with injected Qwen output."""

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
            max_tokens=config.generation.max_tokens,
            temperature=config.generation.temperature,
        )
        fallback_used = result.fallback_count > 0
        records.append(
            {
                "case_id": case["case_id"],
                "prompt_id": f"controlled-{index:03d}",
                "prompt_hash": _short_hash(prompt),
                "prompt_summary": _summarize_text(prompt),
                "controlled_qwen_draft": case["raw_draft"],
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
                "gemma_fallback_used": fallback_used,
                "latency_seconds": result.latency_seconds,
                "qwen_output_summary": _summarize_text(result.raw_draft_text),
                "gemma_output_summary": _summarize_text(result.gemma_output_text),
            }
        )
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


def _summarize_text(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= SUMMARY_LIMIT:
        return compact
    return f"{compact[: SUMMARY_LIMIT - 3]}..."


class _FixedDraftBackend:
    def __init__(self, text: str) -> None:
        self.text = text

    def generate_text(self, prompt: str, *, max_tokens: int, temperature: float, stop=None) -> TextGenerationResult:
        return TextGenerationResult(text=self.text, completion_tokens=None)
