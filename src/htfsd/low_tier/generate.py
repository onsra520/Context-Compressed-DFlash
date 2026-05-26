"""User-facing low-tier block-cycle generation pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Sequence
import time

from htfsd.metrics.cycle_trace_schema import short_hash, summarize_text
from htfsd.text_bridge.normalization import normalize_qwen_draft


GENERATE_NON_CLAIMS: tuple[str, ...] = (
    "This is not a benchmark report.",
    "This is not a performance comparison.",
    "This is not D-Flash correctness validation.",
    "No speedup claim is made.",
    "No performance-improvement claim is made.",
    "No output parity claim is made.",
    "No target-equivalence claim is made.",
    "No correctness claim is made.",
    "No lossless-generation claim is made.",
    "No draft-acceptance metric is reported.",
    "No high-tier implementation claim is made.",
)

GENERATE_INTERPRETATION_GUARDS: tuple[str, ...] = (
    "bridge_valid_block_count is a bridge-level structural diagnostic count only.",
    "It is not accepted block count.",
    "It is not accepted token count.",
    "It is not acceptance-rate evidence.",
    "It is not target-equivalence evidence.",
    "cycle_fallback_count is a cycle-level fallback count only.",
    "It is not correctness evidence.",
    "It is not performance evidence.",
    "It is not benchmark evidence.",
    "It is not a quality score.",
)


@dataclass(frozen=True)
class LowTierGenerateCycle:
    """One generated low-tier block cycle."""

    cycle_id: int
    draft_block_size: int
    draft_text_summary: str
    verifier_text_summary: str
    bridge_status: str
    rejection_reason: str | None
    cycle_fallback_count: int
    drafter_latency_seconds: float
    verifier_latency_seconds: float
    bridge_latency_seconds: float
    context_length_before: int
    context_length_after: int
    response_chars_after: int
    draft_text_chunk: str | None = None
    normalized_draft_text: str | None = None
    verifier_text_chunk: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        optional_raw_fields = {"draft_text_chunk", "normalized_draft_text", "verifier_text_chunk"}
        return {
            key: value
            for key, value in data.items()
            if value is not None or key not in optional_raw_fields
        }


@dataclass(frozen=True)
class LowTierGenerateResult:
    """Result for one prompt through the low-tier block-cycle generation path."""

    prompt: str
    response_text: str
    prompt_hash: str
    prompt_mode: str
    draft_block_size: int
    max_cycles: int
    max_total_chars: int | None
    capture_raw_output: bool
    total_cycles: int
    bridge_valid_block_count: int
    bridge_rejected_block_count: int
    cycle_fallback_count: int
    cycles: list[LowTierGenerateCycle]
    metrics: dict[str, float | int | None]
    interpretation_guards: list[str] = field(default_factory=lambda: list(GENERATE_INTERPRETATION_GUARDS))
    non_claims: list[str] = field(default_factory=lambda: list(GENERATE_NON_CLAIMS))
    trace_path: str | None = None
    trace_type: str = "low_tier_cycle_generate"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["cycles"] = [cycle.to_dict() for cycle in self.cycles]
        if self.trace_path is None:
            data.pop("trace_path")
        return data


def run_low_tier_generate(
    *,
    prompt: str,
    prompt_mode: str,
    drafter_backend,
    verifier_backend,
    draft_block_size: int,
    max_cycles: int,
    max_total_chars: int | None,
    temperature: float,
    stop: Sequence[str] | None,
    capture_raw_output: bool,
) -> LowTierGenerateResult:
    """Run one prompt through the low-tier block-cycle generation path."""

    start = time.perf_counter()
    current_context = prompt
    response_parts: list[str] = []
    cycles: list[LowTierGenerateCycle] = []
    drafter_latency_total = 0.0
    verifier_latency_total = 0.0
    bridge_latency_total = 0.0

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
        drafter_latency_total += drafter_latency

        bridge_start = time.perf_counter()
        bridge = normalize_qwen_draft(draft_result.text)
        bridge_latency = time.perf_counter() - bridge_start
        bridge_latency_total += bridge_latency

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
        verifier_latency_total += verifier_latency

        if bridge.bridge_status == "valid":
            response_chunk = _join_text(bridge.normalized_text, verifier_result.text)
        else:
            response_chunk = verifier_result.text
        response_parts.append(response_chunk)
        current_context = _join_text(current_context, response_chunk)
        response_text = _join_text_sequence(response_parts)
        cycles.append(
            LowTierGenerateCycle(
                cycle_id=cycle_id,
                draft_block_size=draft_block_size,
                draft_text_summary=summarize_text(draft_result.text),
                verifier_text_summary=summarize_text(verifier_result.text),
                bridge_status=bridge.bridge_status,
                rejection_reason=bridge.rejection_reason,
                cycle_fallback_count=cycle_fallback_count,
                drafter_latency_seconds=drafter_latency,
                verifier_latency_seconds=verifier_latency,
                bridge_latency_seconds=bridge_latency,
                context_length_before=context_length_before,
                context_length_after=len(current_context),
                response_chars_after=len(response_text),
                draft_text_chunk=draft_result.text if capture_raw_output else None,
                normalized_draft_text=bridge.normalized_text if capture_raw_output else None,
                verifier_text_chunk=verifier_result.text if capture_raw_output else None,
            )
        )
        if max_total_chars is not None and len(response_text) >= max_total_chars:
            break

    response_text = _join_text_sequence(response_parts)
    total_wall_time = time.perf_counter() - start
    valid_count = sum(1 for cycle in cycles if cycle.bridge_status == "valid")
    rejected_count = sum(1 for cycle in cycles if cycle.bridge_status == "rejected")
    fallback_count = sum(cycle.cycle_fallback_count for cycle in cycles)
    metrics: dict[str, float | int | None] = {
        "total_wall_time_seconds": total_wall_time,
        "drafter_latency_seconds_total": drafter_latency_total,
        "verifier_latency_seconds_total": verifier_latency_total,
        "bridge_latency_seconds_total": bridge_latency_total,
        "output_chars": len(response_text),
        "response_chars": len(response_text),
        "draft_text_chunk_count": len(cycles),
        "verifier_text_chunk_count": len(cycles),
        "tokens_per_second_descriptive": None,
        "latency_seconds_descriptive": total_wall_time,
    }
    return LowTierGenerateResult(
        prompt=prompt,
        response_text=response_text,
        prompt_hash=short_hash(prompt),
        prompt_mode=prompt_mode,
        draft_block_size=draft_block_size,
        max_cycles=max_cycles,
        max_total_chars=max_total_chars,
        capture_raw_output=capture_raw_output,
        total_cycles=len(cycles),
        bridge_valid_block_count=valid_count,
        bridge_rejected_block_count=rejected_count,
        cycle_fallback_count=fallback_count,
        cycles=cycles,
        metrics=metrics,
    )


def write_generate_trace_json(*, result: LowTierGenerateResult, output_dir: str | Path) -> Path:
    """Write a low-tier generate trace JSON artifact under ignored local logs."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-low-tier-generate-trace.json"
    data = result.to_dict()
    data["trace_path"] = str(path)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def with_trace_path(result: LowTierGenerateResult, trace_path: str | None) -> LowTierGenerateResult:
    """Return result with a populated trace path."""

    return LowTierGenerateResult(
        prompt=result.prompt,
        response_text=result.response_text,
        prompt_hash=result.prompt_hash,
        prompt_mode=result.prompt_mode,
        draft_block_size=result.draft_block_size,
        max_cycles=result.max_cycles,
        max_total_chars=result.max_total_chars,
        capture_raw_output=result.capture_raw_output,
        total_cycles=result.total_cycles,
        bridge_valid_block_count=result.bridge_valid_block_count,
        bridge_rejected_block_count=result.bridge_rejected_block_count,
        cycle_fallback_count=result.cycle_fallback_count,
        cycles=result.cycles,
        metrics=result.metrics,
        interpretation_guards=result.interpretation_guards,
        non_claims=result.non_claims,
        trace_path=trace_path,
    )


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


def _join_text(left: str, right: str) -> str:
    if not left or left[-1].isspace() or not right:
        return f"{left}{right}"
    return f"{left} {right}"


def _join_text_sequence(parts: list[str]) -> str:
    output = ""
    for part in parts:
        output = _join_text(output, part)
    return output.strip()

