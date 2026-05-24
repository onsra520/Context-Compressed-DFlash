"""Descriptive trace comparison helpers."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any

from htfsd.metrics.trace_schema import validate_trace_file


def compare_trace_files(*, low_tier_path: str | Path, baseline_path: str | Path) -> dict[str, Any]:
    """Compare low-tier and target-baseline traces without benchmark claims."""

    low_path = Path(low_tier_path)
    base_path = Path(baseline_path)
    low_payload = _read_trace(low_path)
    base_payload = _read_trace(base_path)
    low_records = _records(low_payload)
    base_records = _records(base_payload)
    low_schema = validate_trace_file(low_path, mode="live")
    base_schema = validate_trace_file(base_path, mode="target-baseline")
    low_ids = {_prompt_key(record.get("prompt_id")) for record in low_records}
    base_ids = {_prompt_key(record.get("prompt_id")) for record in base_records}
    low_ids.discard("")
    base_ids.discard("")

    return {
        "low_tier_path": str(low_path),
        "baseline_path": str(base_path),
        "low_tier_records": len(low_records),
        "baseline_records": len(base_records),
        "prompt_id_overlap": len(low_ids & base_ids),
        "missing_prompt_ids": sorted(low_ids - base_ids),
        "extra_prompt_ids": sorted(base_ids - low_ids),
        "low_tier_schema_status": "ok" if low_schema.ok else "failed",
        "baseline_schema_status": "ok" if base_schema.ok else "failed",
        "low_tier_total_fallback_count": _sum_int(low_records, "fallback_count"),
        "low_tier_total_draft_valid_count": _sum_int(low_records, "draft_valid_count"),
        "low_tier_total_draft_rejected_count": _sum_int(low_records, "draft_rejected_count"),
        "low_tier_latency_seconds_summary": _latency_summary(low_records),
        "baseline_latency_seconds_summary": _latency_summary(base_records),
        "low_tier_gemma_device_statuses": _unique_values(low_records, "gemma_device_status"),
        "baseline_gemma_device_statuses": _unique_values(base_records, "gemma_device_status"),
        "qwen_device_statuses": _unique_values(low_records, "qwen_device_status"),
        "gemma_model_file_match": _single_value(low_records, "gemma_model_file") == _single_value(base_records, "gemma_model_file"),
    }


def render_trace_comparison_markdown(result: dict[str, Any]) -> str:
    """Render a compact markdown comparison report."""

    return "\n".join(
        [
            "# Trace Comparison Report v0",
            "",
            "## Summary",
            "",
            "Descriptive comparison of low-tier and target-baseline trace metadata.",
            "",
            "## Input Files",
            "",
            f"- Low-tier: `{result['low_tier_path']}`",
            f"- Baseline: `{result['baseline_path']}`",
            "",
            "## Schema Status",
            "",
            f"- low_tier_schema_status: {result['low_tier_schema_status']}",
            f"- baseline_schema_status: {result['baseline_schema_status']}",
            "",
            "## Record Counts",
            "",
            f"- low_tier_records: {result['low_tier_records']}",
            f"- baseline_records: {result['baseline_records']}",
            "",
            "## Prompt ID Coverage",
            "",
            f"- prompt_id_overlap: {result['prompt_id_overlap']}",
            f"- missing_prompt_ids: {result['missing_prompt_ids']}",
            f"- extra_prompt_ids: {result['extra_prompt_ids']}",
            "",
            "## Runtime Policy Metadata",
            "",
            f"- qwen_device_statuses: {result['qwen_device_statuses']}",
            f"- low_tier_gemma_device_statuses: {result['low_tier_gemma_device_statuses']}",
            f"- baseline_gemma_device_statuses: {result['baseline_gemma_device_statuses']}",
            f"- gemma_model_file_match: {result['gemma_model_file_match']}",
            "",
            "## Low-Tier Bridge Accounting",
            "",
            f"- low_tier_total_fallback_count: {result['low_tier_total_fallback_count']}",
            f"- low_tier_total_draft_valid_count: {result['low_tier_total_draft_valid_count']}",
            f"- low_tier_total_draft_rejected_count: {result['low_tier_total_draft_rejected_count']}",
            "",
            "## Descriptive Latency Fields",
            "",
            f"- low_tier_latency_seconds_summary: {result['low_tier_latency_seconds_summary']}",
            f"- baseline_latency_seconds_summary: {result['baseline_latency_seconds_summary']}",
            "",
            "## Non-Claims",
            "",
            "This is not a benchmark.",
            "No performance-improvement claim is made.",
            "No output-equivalence claim is made.",
            "No draft-acceptance metric is reported.",
            "",
            "## Conclusion",
            "",
            "Trace comparison report v0 completed.",
            "",
        ]
    )


def write_trace_comparison_markdown(*, result: dict[str, Any], output_dir: str | Path) -> Path:
    """Write the markdown comparison report under an output directory."""

    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    report_path = path / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-trace-comparison-v0.md"
    report_path.write_text(render_trace_comparison_markdown(result), encoding="utf-8")
    return report_path


def _read_trace(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = payload.get("records", [])
    return [record for record in records if isinstance(record, dict)] if isinstance(records, list) else []


def _prompt_key(prompt_id: Any) -> str:
    if not isinstance(prompt_id, str):
        return ""
    match = re.search(r"(\d+)$", prompt_id)
    return match.group(1) if match else prompt_id


def _sum_int(records: list[dict[str, Any]], field: str) -> int:
    return sum(int(record.get(field) or 0) for record in records)


def _latency_summary(records: list[dict[str, Any]]) -> dict[str, float | int | None]:
    values = [float(record["latency_seconds"]) for record in records if isinstance(record.get("latency_seconds"), int | float)]
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
    }


def _unique_values(records: list[dict[str, Any]], field: str) -> list[Any]:
    return sorted({record.get(field) for record in records if record.get(field) is not None})


def _single_value(records: list[dict[str, Any]], field: str) -> Any:
    values = _unique_values(records, field)
    return values[0] if len(values) == 1 else None
