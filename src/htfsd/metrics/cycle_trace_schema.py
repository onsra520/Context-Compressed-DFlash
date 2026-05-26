"""Schema and writer for low-tier block-cycle traces."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any


CYCLE_NON_CLAIMS: tuple[str, ...] = (
    "This is not output equality validation.",
    "No output parity claim is made.",
    "No target-equivalence claim is made.",
    "No correctness claim is made.",
    "No lossless-generation claim is made.",
    "No benchmark claim is made.",
    "No performance-improvement claim is made.",
    "No draft-acceptance metric is reported.",
    "No high-tier implementation claim is made.",
    "This is D-Flash shape alignment, not final D-Flash correctness.",
    "This is block-cycle trace scaffolding, not benchmark evidence.",
    "No speedup claim is made.",
    "No acceptance-rate claim is made.",
)


@dataclass(frozen=True)
class LowTierCycle:
    """One low-tier draft-block cycle."""

    cycle_id: int
    draft_block_size: int
    draft_text_summary: str
    bridge_status: str
    rejection_reason: str | None
    cycle_fallback_count: int
    drafter_latency_seconds: float
    verifier_latency_seconds: float
    context_length_before: int
    context_length_after: int
    draft_text_chunk: str | None = None
    normalized_draft_text: str | None = None
    verifier_raw_output: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-friendly cycle data."""

        data = asdict(self)
        optional_raw_fields = {"draft_text_chunk", "normalized_draft_text", "verifier_raw_output"}
        return {
            key: value
            for key, value in data.items()
            if value is not None or key not in optional_raw_fields
        }


@dataclass(frozen=True)
class LowTierCycleTraceRecord:
    """Run-level low-tier cycle trace record for one prompt."""

    prompt_id: str
    prompt_summary: str
    prompt_hash: str
    prompt_set_id: str
    prompt_mode: str
    capture_raw_output: bool
    draft_block_size: int
    max_cycles: int
    max_total_tokens: int | None
    total_cycles: int
    bridge_valid_block_count: int
    bridge_rejected_block_count: int
    cycle_fallback_count: int
    runtime_policy: str
    drafter_device_status: str | None
    verifier_device_status: str | None
    drafter_model_file: str | None
    verifier_model_file: str | None
    cycles: list[LowTierCycle] = field(default_factory=list)
    trace_type: str = "low_tier_cycle_trace"
    non_claims: list[str] = field(default_factory=lambda: list(CYCLE_NON_CLAIMS))

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-friendly trace data."""

        data = asdict(self)
        data["cycles"] = [cycle.to_dict() for cycle in self.cycles]
        return data


def write_cycle_trace_json(
    *,
    records: list[LowTierCycleTraceRecord],
    output_dir: str | Path,
    metadata: dict[str, Any],
) -> Path:
    """Write low-tier cycle trace JSON under the requested output directory."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-low-tier-cycle-trace.json"
    payload = {
        "metadata": metadata,
        "records": [record.to_dict() for record in records],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def short_hash(text: str) -> str:
    """Return a short stable hash for prompt text."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def summarize_text(text: str, limit: int = 120) -> str:
    """Return a compact text summary."""

    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."
