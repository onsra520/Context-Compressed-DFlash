"""Precheck helpers for controlled output comparison preparation."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any

from htfsd.metrics.trace_schema import validate_trace_file


NORMALIZATION_POLICY = {
    "preserve_original_raw_output": True,
    "normalize_crlf_to_lf": True,
    "strip_leading_trailing_whitespace": True,
    "collapse_repeated_whitespace": False,
    "remove_semantic_content": False,
    "remove_model_specific_content": False,
}


def prepare_output_comparison_precheck(*, low_tier_path: str | Path, baseline_path: str | Path) -> dict[str, Any]:
    """Inspect raw-capture traces and report readiness without comparing outputs."""

    low_path = Path(low_tier_path)
    base_path = Path(baseline_path)
    low_payload = _read_trace(low_path)
    base_payload = _read_trace(base_path)
    low_records = _records(low_payload)
    base_records = _records(base_payload)
    low_schema = validate_trace_file(low_path, mode="live")
    base_schema = validate_trace_file(base_path, mode="target-baseline")
    low_ids = _prompt_keys(low_records)
    base_ids = _prompt_keys(base_records)
    low_settings = _single_value(low_records, "generation_settings")
    base_settings = _single_value(base_records, "generation_settings")

    schema_ok = low_schema.ok and base_schema.ok
    low_raw_capture = _raw_capture_enabled(low_payload, low_records)
    base_raw_capture = _raw_capture_enabled(base_payload, base_records)
    raw_capture_ok = low_raw_capture and base_raw_capture
    prompt_coverage_ok = low_ids == base_ids and bool(low_ids)
    settings_ok = isinstance(low_settings, dict) and isinstance(base_settings, dict) and low_settings == base_settings
    runtime_ok = _runtime_metadata_matches(low_records, base_records)
    raw_fields_ok = _raw_fields_present(low_records, ("raw_prompt", "qwen_raw_output", "gemma_raw_output")) and _raw_fields_present(
        base_records,
        ("raw_prompt", "baseline_raw_output"),
    )

    blocking_reasons: list[str] = []
    if not schema_ok:
        blocking_reasons.append("schema_validation_failed")
    if not raw_capture_ok:
        blocking_reasons.append("raw_capture_missing")
    if not prompt_coverage_ok:
        blocking_reasons.append("prompt_coverage_mismatch")
    if not settings_ok:
        blocking_reasons.append("generation_settings_mismatch")
    if not runtime_ok:
        blocking_reasons.append("runtime_metadata_mismatch")
    if not raw_fields_ok:
        blocking_reasons.append("raw_fields_missing")

    return {
        "low_tier_path": str(low_path),
        "baseline_path": str(base_path),
        "output_comparison_ready": not blocking_reasons,
        "schema_status": {"low_tier": "ok" if low_schema.ok else "failed", "baseline": "ok" if base_schema.ok else "failed"},
        "raw_capture_status": {"low_tier": low_raw_capture, "baseline": base_raw_capture},
        "prompt_coverage_status": "ok" if prompt_coverage_ok else "failed",
        "prompt_id_overlap": len(low_ids & base_ids),
        "missing_prompt_ids": sorted(low_ids - base_ids),
        "extra_prompt_ids": sorted(base_ids - low_ids),
        "generation_settings_match": settings_ok,
        "generation_settings_fields": {
            "max_tokens_match": _settings_field_matches(low_settings, base_settings, "max_tokens"),
            "temperature_match": _settings_field_matches(low_settings, base_settings, "temperature"),
            "seed_match": _settings_field_matches(low_settings, base_settings, "seed"),
            "stop_match": _settings_field_matches(low_settings, base_settings, "stop"),
            "prompt_mode_match": _settings_field_matches(low_settings, base_settings, "prompt_mode"),
        },
        "runtime_metadata_match": runtime_ok,
        "runtime_metadata": {
            "verifier_model_file_match": _single_value(low_records, "verifier_model_file", "gemma_model_file")
            == _single_value(base_records, "verifier_model_file", "gemma_model_file"),
            "low_tier_verifier_device_statuses": _unique_values(low_records, "verifier_device_status", "gemma_device_status"),
            "baseline_verifier_device_statuses": _unique_values(base_records, "verifier_device_status", "gemma_device_status"),
            "gemma_model_file_match": _single_value(low_records, "verifier_model_file", "gemma_model_file")
            == _single_value(base_records, "verifier_model_file", "gemma_model_file"),
            "low_tier_gemma_device_statuses": _unique_values(low_records, "verifier_device_status", "gemma_device_status"),
            "baseline_gemma_device_statuses": _unique_values(base_records, "verifier_device_status", "gemma_device_status"),
        },
        "raw_field_presence_status": "ok" if raw_fields_ok else "failed",
        "normalization_policy": NORMALIZATION_POLICY,
        "blocking_reasons": blocking_reasons,
        "normalized_output_preview": _normalization_previews(low_records, base_records),
    }


def normalize_output_preview(text: str, *, collapse_repeated_whitespace: bool = False) -> str:
    """Conservatively normalize output for preview only."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if collapse_repeated_whitespace:
        normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def render_output_comparison_precheck_markdown(result: dict[str, Any]) -> str:
    """Render a compact markdown precheck report."""

    ready = "yes" if result["output_comparison_ready"] else "no"
    return "\n".join(
        [
            "# Output Comparison Precheck",
            "",
            "## Summary",
            "",
            "Controlled output comparison readiness precheck.",
            "",
            "## Input Files",
            "",
            f"- Low-tier: `{result['low_tier_path']}`",
            f"- Baseline: `{result['baseline_path']}`",
            "",
            "## Schema Status",
            "",
            f"- schema_status: {result['schema_status']}",
            "",
            "## Raw Capture Status",
            "",
            f"- raw_capture_status: {result['raw_capture_status']}",
            "",
            "## Prompt Coverage",
            "",
            f"- prompt_coverage_status: {result['prompt_coverage_status']}",
            f"- prompt_id_overlap: {result['prompt_id_overlap']}",
            f"- missing_prompt_ids: {result['missing_prompt_ids']}",
            f"- extra_prompt_ids: {result['extra_prompt_ids']}",
            "",
            "## Generation Settings Match",
            "",
            f"- generation_settings_match: {result['generation_settings_match']}",
            f"- generation_settings_fields: {result['generation_settings_fields']}",
            "",
            "## Runtime Metadata Match",
            "",
            f"- runtime_metadata_match: {result['runtime_metadata_match']}",
            f"- runtime_metadata: {result['runtime_metadata']}",
            "",
            "## Raw Field Presence",
            "",
            f"- raw_field_presence_status: {result['raw_field_presence_status']}",
            "",
            "## Normalization Policy",
            "",
            f"- normalization_policy: {result['normalization_policy']}",
            "",
            "## Readiness",
            "",
            f"- output_comparison_ready: {ready}",
            f"- blocking_reasons: {result['blocking_reasons']}",
            "",
            "## Non-Claims",
            "",
            "This is not an output equality report.",
            "No output parity claim is made.",
            "No exact-generation claim is made.",
            "No benchmark claim is made.",
            "",
        ]
    )


def write_output_comparison_precheck_reports(*, result: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
    """Write markdown and JSON precheck reports."""

    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    markdown_path = path / f"{timestamp}-output-comparison-precheck.md"
    json_path = path / f"{timestamp}-output-comparison-precheck.json"
    markdown_path.write_text(render_output_comparison_precheck_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return markdown_path, json_path


def _read_trace(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = payload.get("records", [])
    return [record for record in records if isinstance(record, dict)] if isinstance(records, list) else []


def _prompt_keys(records: list[dict[str, Any]]) -> set[str]:
    keys = {_prompt_key(record.get("prompt_id")) for record in records}
    keys.discard("")
    return keys


def _prompt_key(prompt_id: Any) -> str:
    if not isinstance(prompt_id, str):
        return ""
    match = re.search(r"(\d+)$", prompt_id)
    return match.group(1) if match else prompt_id


def _raw_capture_enabled(payload: dict[str, Any], records: list[dict[str, Any]]) -> bool:
    metadata = payload.get("metadata", {})
    metadata_enabled = isinstance(metadata, dict) and metadata.get("capture_raw_output") is True
    record_values = [record.get("capture_raw_output") for record in records]
    return metadata_enabled and bool(record_values) and all(value is True for value in record_values)


def _raw_fields_present(records: list[dict[str, Any]], fields: tuple[str, ...]) -> bool:
    return bool(records) and all(all(field in record for field in fields) for record in records)


def _runtime_metadata_matches(low_records: list[dict[str, Any]], base_records: list[dict[str, Any]]) -> bool:
    low_gemma_file = _single_value(low_records, "verifier_model_file", "gemma_model_file")
    base_gemma_file = _single_value(base_records, "verifier_model_file", "gemma_model_file")
    return (
        low_gemma_file is not None
        and low_gemma_file == base_gemma_file
        and _unique_values(low_records, "verifier_device_status", "gemma_device_status") == ["ok"]
        and _unique_values(base_records, "verifier_device_status", "gemma_device_status") == ["ok"]
    )


def _single_value(records: list[dict[str, Any]], field: str, alias: str | None = None) -> Any:
    values = [_record_value(record, field, alias) for record in records if _record_value(record, field, alias) is not None]
    if not values:
        return None
    first = values[0]
    if all(_stable_value_key(value) == _stable_value_key(first) for value in values):
        return first
    return None


def _unique_values(records: list[dict[str, Any]], field: str, alias: str | None = None) -> list[Any]:
    return sorted({_record_value(record, field, alias) for record in records if _record_value(record, field, alias) is not None})


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


def _normalization_previews(low_records: list[dict[str, Any]], base_records: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    return {
        "low_tier": [
            {
                "prompt_id": str(record.get("prompt_id", "")),
                "gemma_raw_output_preview": normalize_output_preview(str(record.get("gemma_raw_output", ""))),
            }
            for record in low_records
            if "gemma_raw_output" in record
        ],
        "baseline": [
            {
                "prompt_id": str(record.get("prompt_id", "")),
                "baseline_raw_output_preview": normalize_output_preview(str(record.get("baseline_raw_output", ""))),
            }
            for record in base_records
            if "baseline_raw_output" in record
        ],
    }
