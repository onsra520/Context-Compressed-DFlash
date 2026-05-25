"""Eligible-record inspection reports for selected valid-draft diagnostic records."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from htfsd.metrics.diagnostic_record_selection import (
    DEFAULT_PREVIEW_MAX_CHARS,
    DiagnosticRecordSelectionSummary,
    select_diagnostic_records_from_traces,
)
from htfsd.metrics.output_preview import build_output_normalization_preview


def build_eligible_record_inspection(
    *,
    low_tier_path: str | Path,
    baseline_path: str | Path,
    preview_max_chars: int = DEFAULT_PREVIEW_MAX_CHARS,
) -> dict[str, Any]:
    """Build a compact inspection report for eligible valid-draft records only."""

    selection_summary = select_diagnostic_records_from_traces(
        low_tier_path=low_tier_path,
        baseline_path=baseline_path,
        preview_max_chars=preview_max_chars,
    )
    preview = build_output_normalization_preview(
        low_tier_path=low_tier_path,
        baseline_path=baseline_path,
        preview_max_chars=preview_max_chars,
    )
    low_records = _trace_records(Path(low_tier_path))
    low_by_prompt = {str(record.get("prompt_id") or "<unknown>"): record for record in low_records}
    preview_by_prompt = {record["prompt_id"]: record for record in preview["preview_records"]}
    eligible_records = _eligible_records(
        selection_summary=selection_summary,
        low_by_prompt=low_by_prompt,
        preview_by_prompt=preview_by_prompt,
    )
    return {
        "low_tier_path": str(Path(low_tier_path)),
        "baseline_path": str(Path(baseline_path)),
        "inspection_ready": selection_summary.selection_ready,
        "blocking_reasons": selection_summary.blocking_reasons or [],
        "selector_status": {
            "selection_ready": selection_summary.selection_ready,
            "total_records": selection_summary.total_records,
            "eligible_valid_draft_record_count": selection_summary.eligible_valid_draft_record_count,
            "excluded_fallback_derived_record_count": selection_summary.excluded_fallback_derived_record_count,
            "excluded_unknown_contribution_record_count": selection_summary.excluded_unknown_contribution_record_count,
            "excluded_empty_baseline_record_count": selection_summary.excluded_empty_baseline_record_count,
            "excluded_prompt_mode_risk_record_count": selection_summary.excluded_prompt_mode_risk_record_count,
            "eligible_prompt_ids": selection_summary.eligible_prompt_ids,
            "excluded_prompt_ids_by_reason": selection_summary.excluded_prompt_ids_by_reason,
        },
        "eligible_record_count": len(eligible_records),
        "eligible_records": eligible_records,
        "excluded_record_summary": _excluded_record_summary(selection_summary),
        "warnings": selection_summary.warnings,
        "preview_max_chars": preview_max_chars,
    }


def render_eligible_record_inspection_markdown(result: dict[str, Any]) -> str:
    """Render eligible-record inspection as markdown."""

    ready = "yes" if result["inspection_ready"] else "no"
    lines = [
        "# Eligible Record Inspection",
        "",
        "## Summary",
        "",
        "Compact inspection metadata for records selected as eligible valid-draft records.",
        "",
        "## Input Files",
        "",
        f"- Low-tier: `{result['low_tier_path']}`",
        f"- Baseline: `{result['baseline_path']}`",
        "",
        "## Selector Status",
        "",
        f"- inspection_ready: {ready}",
        f"- blocking_reasons: {result['blocking_reasons']}",
        f"- selector_status: {result['selector_status']}",
        "",
        "## Eligible Record Counts",
        "",
        f"- eligible_record_count: {result['eligible_record_count']}",
        "",
        "## Eligible Records",
        "",
    ]
    if result["eligible_records"]:
        for record in result["eligible_records"]:
            lines.extend(
                [
                    f"### {record['prompt_id']}",
                    "",
                    f"- prompt_summary: {record.get('prompt_summary')}",
                    f"- prompt_hash: {record.get('prompt_hash')}",
                    f"- selection_category: {record['selection_category']}",
                    f"- contribution_category: {record['contribution_category']}",
                    f"- bridge_status: {record['bridge_status']}",
                    f"- fallback_count: {record['fallback_count']}",
                    f"- draft_valid_count: {record['draft_valid_count']}",
                    f"- draft_rejected_count: {record['draft_rejected_count']}",
                    f"- low_tier_normalized_length: {record['low_tier_normalized_length']}",
                    f"- baseline_normalized_length: {record['baseline_normalized_length']}",
                    f"- diagnostic exact-string flag: {record['normalized_outputs_exact_string_match']}",
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
                    f"- warnings: {record['warnings']}",
                    "",
                ]
            )
    else:
        lines.extend(["No eligible records were selected.", ""])
    lines.extend(
        [
            "## Excluded Record Summary",
            "",
            f"- excluded_record_summary: {result['excluded_record_summary']}",
            "",
            "## Warnings",
            "",
            f"- warnings: {result['warnings']}",
            "",
            "## Non-Claims",
            "",
            "This is not an output equality report.",
            "No output parity claim is made.",
            "No target-equivalence claim is made.",
            "No correctness claim is made.",
            "No lossless-generation claim is made.",
            "No benchmark claim is made.",
            "No draft-acceptance metric is reported.",
            "",
            "## Conclusion",
            "",
            "Eligible record inspection generated for compact inspection only."
            if result["inspection_ready"]
            else "Eligible record inspection blocked by selector readiness.",
            "",
        ]
    )
    return "\n".join(lines)


def write_eligible_record_inspection_reports(*, result: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
    """Write markdown and JSON eligible-record inspection reports."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-eligible-record-inspection"
    markdown_path = _next_report_path(directory, stem, ".md")
    json_path = _next_report_path(directory, stem, ".json")
    markdown_path.write_text(render_eligible_record_inspection_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return markdown_path, json_path


def _eligible_records(
    *,
    selection_summary: DiagnosticRecordSelectionSummary,
    low_by_prompt: dict[str, dict[str, Any]],
    preview_by_prompt: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for selection in selection_summary.selections:
        if not selection.eligible_for_draft_contribution_diagnostic:
            continue
        low = low_by_prompt.get(selection.prompt_id, {})
        preview = preview_by_prompt.get(selection.prompt_id, {})
        records.append(
            {
                "prompt_id": selection.prompt_id,
                "prompt_summary": low.get("prompt_summary") or preview.get("prompt_summary"),
                "prompt_hash": low.get("prompt_hash") or preview.get("prompt_hash"),
                "selection_category": selection.selection_category,
                "contribution_category": selection.contribution_category,
                "bridge_status": low.get("bridge_status"),
                "fallback_count": low.get("fallback_count"),
                "draft_valid_count": low.get("draft_valid_count"),
                "draft_rejected_count": low.get("draft_rejected_count"),
                "low_tier_normalized_length": preview.get("low_tier_normalized_length"),
                "baseline_normalized_length": preview.get("baseline_normalized_length"),
                "normalized_outputs_exact_string_match": preview.get("normalized_outputs_exact_string_match"),
                "low_tier_preview": preview.get("low_tier_preview"),
                "baseline_preview": preview.get("baseline_preview"),
                "warnings": selection.warnings,
            }
        )
    return records


def _excluded_record_summary(selection_summary: DiagnosticRecordSelectionSummary) -> dict[str, Any]:
    return {
        "excluded_fallback_derived_record_count": selection_summary.excluded_fallback_derived_record_count,
        "excluded_unknown_contribution_record_count": selection_summary.excluded_unknown_contribution_record_count,
        "excluded_empty_baseline_record_count": selection_summary.excluded_empty_baseline_record_count,
        "excluded_prompt_mode_risk_record_count": selection_summary.excluded_prompt_mode_risk_record_count,
        "excluded_prompt_ids_by_reason": selection_summary.excluded_prompt_ids_by_reason,
    }


def _trace_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    return [record for record in records if isinstance(record, dict)] if isinstance(records, list) else []


def _next_report_path(directory: Path, stem: str, suffix: str) -> Path:
    path = directory / f"{stem}{suffix}"
    if not path.exists():
        return path
    index = 2
    while True:
        candidate = directory / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1
