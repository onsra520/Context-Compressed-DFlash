"""Schema guards for low-tier trace records."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Literal

TraceMode = Literal["live", "controlled-fallback"]

SHARED_TRACE_FIELDS = frozenset(
    {
        "prompt_id",
        "bridge_status",
        "rejection_reason",
        "fallback_count",
        "draft_valid_count",
        "draft_rejected_count",
        "qwen_expected_device",
        "gemma_expected_device",
        "qwen_device_status",
        "gemma_device_status",
        "qwen_n_gpu_layers",
        "gemma_n_gpu_layers",
        "qwen_model_file",
        "gemma_model_file",
        "latency_seconds",
    }
)

CONTROLLED_TRACE_FIELDS = frozenset({"case_id", "gemma_fallback_used"})


@dataclass(frozen=True)
class TraceRecordSchemaResult:
    """Schema validation result for one trace record."""

    ok: bool
    missing_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TraceFileSchemaResult:
    """Schema validation result for a trace JSON file."""

    ok: bool
    mode: str
    record_count: int
    record_errors: list[TraceRecordSchemaResult] = field(default_factory=list)


def required_live_trace_fields() -> frozenset[str]:
    """Return fields required on live low-tier trace records."""

    return SHARED_TRACE_FIELDS


def required_controlled_trace_fields() -> frozenset[str]:
    """Return fields required on controlled fallback trace records."""

    return SHARED_TRACE_FIELDS | CONTROLLED_TRACE_FIELDS


def validate_trace_record(record: dict[str, Any], *, mode: TraceMode) -> TraceRecordSchemaResult:
    """Validate one trace record has all fields required for its mode."""

    required = required_controlled_trace_fields() if mode == "controlled-fallback" else required_live_trace_fields()
    missing = sorted(field_name for field_name in required if field_name not in record)
    return TraceRecordSchemaResult(ok=not missing, missing_fields=missing)


def validate_trace_file(path: str | Path, *, mode: TraceMode) -> TraceFileSchemaResult:
    """Validate every record in a compact trace JSON file."""

    trace_path = Path(path)
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    if not isinstance(records, list):
        records = []
    record_errors = [
        result
        for result in (validate_trace_record(record, mode=mode) for record in records if isinstance(record, dict))
        if not result.ok
    ]
    return TraceFileSchemaResult(
        ok=not record_errors,
        mode=mode,
        record_count=len(records),
        record_errors=record_errors,
    )
