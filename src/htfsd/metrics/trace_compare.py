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

    low_settings = _single_value(low_records, "generation_settings")
    base_settings = _single_value(base_records, "generation_settings")
    settings_available = isinstance(low_settings, dict) and isinstance(base_settings, dict)
    generation_settings_match = settings_available and low_settings == base_settings

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
        "low_tier_verifier_device_statuses": _unique_values(low_records, "verifier_device_status", "gemma_device_status"),
        "baseline_verifier_device_statuses": _unique_values(base_records, "verifier_device_status", "gemma_device_status"),
        "drafter_device_statuses": _unique_values(low_records, "drafter_device_status", "qwen_device_status"),
        "verifier_model_file_match": _single_value(low_records, "verifier_model_file", "gemma_model_file")
        == _single_value(base_records, "verifier_model_file", "gemma_model_file"),
        "low_tier_gemma_device_statuses": _unique_values(low_records, "verifier_device_status", "gemma_device_status"),
        "baseline_gemma_device_statuses": _unique_values(base_records, "verifier_device_status", "gemma_device_status"),
        "qwen_device_statuses": _unique_values(low_records, "drafter_device_status", "qwen_device_status"),
        "gemma_model_file_match": _single_value(low_records, "verifier_model_file", "gemma_model_file")
        == _single_value(base_records, "verifier_model_file", "gemma_model_file"),
        "generation_settings_match": generation_settings_match,
        "capture_raw_output_status": {
            "low_tier": _unique_values(low_records, "capture_raw_output"),
            "baseline": _unique_values(base_records, "capture_raw_output"),
        },
        "max_tokens_match": _settings_field_matches(low_settings, base_settings, "max_tokens"),
        "temperature_match": _settings_field_matches(low_settings, base_settings, "temperature"),
        "prompt_mode_match": _settings_field_matches(low_settings, base_settings, "prompt_mode"),
        "stop_match": _settings_field_matches(low_settings, base_settings, "stop"),
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
            f"- drafter_device_statuses: {result['drafter_device_statuses']}",
            f"- low_tier_verifier_device_statuses: {result['low_tier_verifier_device_statuses']}",
            f"- baseline_verifier_device_statuses: {result['baseline_verifier_device_statuses']}",
            f"- verifier_model_file_match: {result['verifier_model_file_match']}",
            "",
            "## Generation Settings Metadata",
            "",
            f"- generation_settings_match: {result['generation_settings_match']}",
            f"- capture_raw_output_status: {result['capture_raw_output_status']}",
            f"- max_tokens_match: {result['max_tokens_match']}",
            f"- temperature_match: {result['temperature_match']}",
            f"- prompt_mode_match: {result['prompt_mode_match']}",
            f"- stop_match: {result['stop_match']}",
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


def _unique_values(records: list[dict[str, Any]], field: str, alias: str | None = None) -> list[Any]:
    return sorted({_record_value(record, field, alias) for record in records if _record_value(record, field, alias) is not None})


def _single_value(records: list[dict[str, Any]], field: str, alias: str | None = None) -> Any:
    values = [_record_value(record, field, alias) for record in records if _record_value(record, field, alias) is not None]
    if not values:
        return None
    first = values[0]
    if all(_stable_value_key(value) == _stable_value_key(first) for value in values):
        return first
    return None


def _record_value(record: dict[str, Any], field: str, alias: str | None) -> Any:
    if field in record:
        return record.get(field)
    if alias is not None:
        return record.get(alias)
    return None


def _settings_field_matches(left: Any, right: Any, field: str) -> bool:
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    return left.get(field) == right.get(field)


def _stable_value_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)
