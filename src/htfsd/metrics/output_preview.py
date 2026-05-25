"""Output normalization preview helpers for raw-capture traces."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any

from htfsd.metrics.output_compare import (
    NORMALIZATION_POLICY,
    normalize_output_preview,
    prepare_output_comparison_precheck,
)


DEFAULT_PREVIEW_MAX_CHARS = 200


def build_output_normalization_preview(
    *,
    low_tier_path: str | Path,
    baseline_path: str | Path,
    preview_max_chars: int = DEFAULT_PREVIEW_MAX_CHARS,
) -> dict[str, Any]:
    """Build conservative normalized output previews after precheck readiness passes."""

    precheck = prepare_output_comparison_precheck(low_tier_path=low_tier_path, baseline_path=baseline_path)
    result: dict[str, Any] = {
        "low_tier_path": str(Path(low_tier_path)),
        "baseline_path": str(Path(baseline_path)),
        "preview_ready": precheck["output_comparison_ready"],
        "blocking_reasons": precheck["blocking_reasons"],
        "precheck": _compact_precheck(precheck),
        "normalization_policy": NORMALIZATION_POLICY,
        "preview_max_chars": preview_max_chars,
        "preview_records": [],
        "output_health": _output_health([]),
    }
    if not precheck["output_comparison_ready"]:
        return result

    low_records = _records(_read_trace(Path(low_tier_path)))
    baseline_records = _records(_read_trace(Path(baseline_path)))
    baseline_by_key = {_prompt_key(record.get("prompt_id")): record for record in baseline_records}
    preview_records: list[dict[str, Any]] = []
    for low_record in sorted(low_records, key=lambda record: _prompt_key(record.get("prompt_id"))):
        key = _prompt_key(low_record.get("prompt_id"))
        baseline_record = baseline_by_key.get(key)
        if baseline_record is None:
            continue
        low_output = low_record.get("gemma_raw_output")
        baseline_output = baseline_record.get("baseline_raw_output")
        low_normalized = normalize_output_preview(str(low_output)) if low_output is not None else ""
        baseline_normalized = normalize_output_preview(str(baseline_output)) if baseline_output is not None else ""
        preview_records.append(
            {
                "prompt_id": str(low_record.get("prompt_id", "")),
                "prompt_summary": low_record.get("prompt_summary") or baseline_record.get("prompt_summary"),
                "prompt_hash": low_record.get("prompt_hash") or baseline_record.get("prompt_hash"),
                "low_tier_output_present": isinstance(low_output, str),
                "baseline_output_present": isinstance(baseline_output, str),
                "low_tier_normalized_length": len(low_normalized),
                "baseline_normalized_length": len(baseline_normalized),
                "low_tier_empty_after_normalization": low_normalized == "",
                "baseline_empty_after_normalization": baseline_normalized == "",
                "normalized_outputs_exact_string_match": low_normalized == baseline_normalized,
                "low_tier_preview": _truncate(low_normalized, preview_max_chars),
                "baseline_preview": _truncate(baseline_normalized, preview_max_chars),
            }
        )
    result["preview_records"] = preview_records
    result["output_health"] = _output_health(preview_records)
    return result


def render_output_normalization_preview_markdown(result: dict[str, Any]) -> str:
    """Render a compact markdown report for human inspection."""

    ready = "yes" if result["preview_ready"] else "no"
    records = result["preview_records"]
    lines = [
        "# Output Normalization Preview",
        "",
        "## Summary",
        "",
        "Conservative normalized output preview for raw-capture traces.",
        "",
        "## Input Files",
        "",
        f"- Low-tier: `{result['low_tier_path']}`",
        f"- Baseline: `{result['baseline_path']}`",
        "",
        "## Precheck Status",
        "",
        f"- preview_ready: {ready}",
        f"- blocking_reasons: {result['blocking_reasons']}",
        f"- precheck: {result['precheck']}",
        "",
        "## Normalization Policy",
        "",
        f"- normalization_policy: {result['normalization_policy']}",
        f"- preview_max_chars: {result['preview_max_chars']}",
        "",
        "## Preview Records",
        "",
    ]
    if records:
        for record in records:
            lines.extend(
                [
                    f"### {record['prompt_id']}",
                    "",
                    f"- prompt_summary: {record.get('prompt_summary')}",
                    f"- low_tier_normalized_length: {record['low_tier_normalized_length']}",
                    f"- baseline_normalized_length: {record['baseline_normalized_length']}",
                    f"- normalized_outputs_exact_string_match: {record['normalized_outputs_exact_string_match']}",
                    "- low_tier_preview:",
                    "",
                    "```text",
                    str(record["low_tier_preview"]),
                    "```",
                    "",
                    "- baseline_preview:",
                    "",
                    "```text",
                    str(record["baseline_preview"]),
                    "```",
                    "",
                ]
            )
    else:
        lines.extend(["No preview records were generated.", ""])
    lines.extend(
        [
            "## Empty Output Flags",
            "",
            f"- empty_flags: {_empty_flags(records)}",
            "",
            "## Exact String Match Preview",
            "",
            f"- exact_string_match_preview: {_match_flags(records)}",
            "",
            "## Output Health Checks",
            "",
            f"- output_health: {result['output_health']}",
            "",
            "## Non-Claims",
            "",
            "This is not an output equality report.",
            "Exact string match preview is not target-equivalence validation.",
            "No output parity claim is made.",
            "No correctness claim is made.",
            "No lossless-generation claim is made.",
            "No benchmark claim is made.",
            "",
            "## Conclusion",
            "",
            "Preview generated for inspection only." if result["preview_ready"] else "Preview blocked by precheck.",
            "",
        ]
    )
    return "\n".join(lines)


def write_output_normalization_preview_reports(*, result: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
    """Write markdown and JSON preview reports."""

    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    markdown_path = path / f"{timestamp}-output-normalization-preview.md"
    json_path = path / f"{timestamp}-output-normalization-preview.json"
    markdown_path.write_text(render_output_normalization_preview_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return markdown_path, json_path


def _compact_precheck(precheck: dict[str, Any]) -> dict[str, Any]:
    return {
        "output_comparison_ready": precheck["output_comparison_ready"],
        "schema_status": precheck["schema_status"],
        "raw_capture_status": precheck["raw_capture_status"],
        "prompt_coverage_status": precheck["prompt_coverage_status"],
        "generation_settings_match": precheck["generation_settings_match"],
        "runtime_metadata_match": precheck["runtime_metadata_match"],
        "raw_field_presence_status": precheck["raw_field_presence_status"],
        "blocking_reasons": precheck["blocking_reasons"],
    }


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


def _truncate(text: str, max_chars: int) -> str:
    if max_chars < 0:
        max_chars = 0
    return text if len(text) <= max_chars else text[:max_chars] + "..."


def _empty_flags(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "prompt_id": record["prompt_id"],
            "low_tier_empty_after_normalization": record["low_tier_empty_after_normalization"],
            "baseline_empty_after_normalization": record["baseline_empty_after_normalization"],
        }
        for record in records
    ]


def _match_flags(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "prompt_id": record["prompt_id"],
            "normalized_outputs_exact_string_match": record["normalized_outputs_exact_string_match"],
        }
        for record in records
    ]


def _output_health(records: list[dict[str, Any]]) -> dict[str, Any]:
    low_empty_count = sum(1 for record in records if record["low_tier_empty_after_normalization"])
    baseline_empty_count = sum(1 for record in records if record["baseline_empty_after_normalization"])
    all_low_present = bool(records) and all(record["low_tier_output_present"] for record in records)
    all_baseline_present = bool(records) and all(record["baseline_output_present"] for record in records)
    warnings: list[str] = []
    prompt_mode_risk = "none"
    if baseline_empty_count:
        prompt_mode_risk = "baseline_empty_outputs"
        warnings.append("baseline outputs contain empty normalized text; output comparison diagnostics may be uninformative")
    elif low_empty_count:
        prompt_mode_risk = "low_tier_empty_outputs"
        warnings.append("low-tier outputs contain empty normalized text; output comparison diagnostics may be uninformative")
    return {
        "low_tier_empty_after_normalization_count": low_empty_count,
        "baseline_empty_after_normalization_count": baseline_empty_count,
        "all_low_tier_outputs_present": all_low_present,
        "all_baseline_outputs_present": all_baseline_present,
        "prompt_mode_risk": prompt_mode_risk,
        "warnings": warnings,
    }
