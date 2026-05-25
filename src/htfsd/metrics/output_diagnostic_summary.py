"""Fallback-aware output diagnostic summary helpers."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from htfsd.metrics.output_diagnostics import (
    ContributionCategory,
    classify_low_tier_trace_file,
)
from htfsd.metrics.output_preview import (
    DEFAULT_PREVIEW_MAX_CHARS,
    build_output_normalization_preview,
)


CATEGORIES: tuple[ContributionCategory, ...] = (
    "valid_draft_continuation",
    "fallback_after_rejection",
    "fallback_only",
    "unknown_contribution",
)

FALLBACK_DERIVED_CATEGORIES = frozenset({"fallback_after_rejection", "fallback_only"})

FALLBACK_DERIVED_WARNING = (
    "This trace contains fallback-derived records. String diagnostics for those records mostly reflect Gemma fallback "
    "behavior, not successful Qwen draft contribution."
)
MAJORITY_FALLBACK_WARNING = (
    "Most low-tier records in this trace are fallback-derived. Draft-contribution diagnostics are limited for this run."
)
UNKNOWN_CONTRIBUTION_WARNING = (
    "Some records have unknown contribution category due to missing or contradictory fields."
)
BASELINE_EMPTY_WARNING = (
    "Some baseline outputs are empty after normalization. Output diagnostics may be uninformative for those prompts."
)
RAW_PROMPT_MODE_WARNING = (
    "Raw prompt mode may produce empty Gemma baseline outputs for this prompt set. Consider chat mode for "
    "output-comparison preparation."
)


def build_fallback_aware_output_diagnostic_summary(
    *,
    low_tier_path: str | Path,
    baseline_path: str | Path,
    preview_max_chars: int = DEFAULT_PREVIEW_MAX_CHARS,
) -> dict[str, Any]:
    """Build a category-grouped diagnostic summary from trace preview and classification metadata."""

    preview = build_output_normalization_preview(
        low_tier_path=low_tier_path,
        baseline_path=baseline_path,
        preview_max_chars=preview_max_chars,
    )
    classification_summary = classify_low_tier_trace_file(low_tier_path)
    classifications = [classification.to_dict() for classification in classification_summary.classifications]
    category_summaries = _category_summaries(
        classifications=classifications,
        preview_records=preview["preview_records"],
    )
    output_health = preview["output_health"]
    precheck = preview["precheck"]
    warnings = _summary_warnings(
        classification_summary=classification_summary.to_dict(),
        output_health=output_health,
        prompt_mode=_trace_prompt_mode(Path(low_tier_path)),
    )
    return {
        "low_tier_path": str(Path(low_tier_path)),
        "baseline_path": str(Path(baseline_path)),
        "summary_ready": preview["preview_ready"],
        "precheck_ready": preview["precheck"]["output_comparison_ready"],
        "blocking_reasons": preview["blocking_reasons"],
        "total_records": classification_summary.total_records,
        "valid_draft_continuation_count": classification_summary.valid_draft_continuation_count,
        "fallback_after_rejection_count": classification_summary.fallback_after_rejection_count,
        "fallback_only_count": classification_summary.fallback_only_count,
        "unknown_contribution_count": classification_summary.unknown_contribution_count,
        "precheck": precheck,
        "generation_settings_match": precheck["generation_settings_match"],
        "prompt_coverage_status": precheck["prompt_coverage_status"],
        "runtime_metadata_match": precheck["runtime_metadata_match"],
        "all_low_tier_outputs_present": output_health["all_low_tier_outputs_present"],
        "all_baseline_outputs_present": output_health["all_baseline_outputs_present"],
        "output_health": output_health,
        "classification_records": classifications,
        "category_summaries": category_summaries,
        "warnings": warnings,
        "preview_max_chars": preview_max_chars,
    }


def render_fallback_aware_output_diagnostic_summary_markdown(summary: dict[str, Any]) -> str:
    """Render the fallback-aware diagnostic summary as markdown."""

    ready = "yes" if summary["summary_ready"] else "no"
    lines = [
        "# Fallback-Aware Output Diagnostic Summary",
        "",
        "## Summary",
        "",
        "Fallback-aware output diagnostic summary grouped by low-tier contribution category.",
        "",
        "## Input Files",
        "",
        f"- Low-tier: `{summary['low_tier_path']}`",
        f"- Baseline: `{summary['baseline_path']}`",
        "",
        "## Precheck Status",
        "",
        f"- summary_ready: {ready}",
        f"- precheck_ready: {'yes' if summary['precheck_ready'] else 'no'}",
        f"- blocking_reasons: {summary['blocking_reasons']}",
        f"- precheck: {summary['precheck']}",
        "",
        "## Contribution Category Counts",
        "",
        f"- total_records: {summary['total_records']}",
        f"- valid_draft_continuation_count: {summary['valid_draft_continuation_count']}",
        f"- fallback_after_rejection_count: {summary['fallback_after_rejection_count']}",
        f"- fallback_only_count: {summary['fallback_only_count']}",
        f"- unknown_contribution_count: {summary['unknown_contribution_count']}",
        "",
        "## Category-Level Diagnostic Fields",
        "",
    ]
    for category in CATEGORIES:
        category_summary = summary["category_summaries"][category]
        lines.extend(
            [
                f"### {category}",
                "",
                f"- record_count: {category_summary['record_count']}",
                f"- prompt_ids: {category_summary['prompt_ids']}",
                f"- empty_low_tier_count: {category_summary['empty_low_tier_count']}",
                f"- empty_baseline_count: {category_summary['empty_baseline_count']}",
                f"- diagnostic_exact_string_match_count: {category_summary['diagnostic_exact_string_match_count']}",
                f"- diagnostic_exact_string_mismatch_count: {category_summary['diagnostic_exact_string_mismatch_count']}",
                f"- warnings: {category_summary['warnings']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Warnings",
            "",
            f"- warnings: {summary['warnings']}",
            "",
            "## Prompt Coverage",
            "",
            f"- prompt_coverage_status: {summary['prompt_coverage_status']}",
            "",
            "## Generation Settings",
            "",
            f"- generation_settings_match: {summary['generation_settings_match']}",
            "",
            "## Runtime Metadata",
            "",
            f"- runtime_metadata_match: {summary['runtime_metadata_match']}",
            f"- all_low_tier_outputs_present: {summary['all_low_tier_outputs_present']}",
            f"- all_baseline_outputs_present: {summary['all_baseline_outputs_present']}",
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
            "Diagnostic summary generated for inspection only." if summary["summary_ready"] else "Diagnostic summary blocked by precheck.",
            "",
        ]
    )
    return "\n".join(lines)


def write_fallback_aware_output_diagnostic_summary_reports(
    *,
    summary: dict[str, Any],
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """Write markdown and JSON summary reports."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-fallback-aware-output-diagnostic-summary"
    markdown_path = _next_report_path(directory, stem, ".md")
    json_path = _next_report_path(directory, stem, ".json")
    markdown_path.write_text(render_fallback_aware_output_diagnostic_summary_markdown(summary), encoding="utf-8")
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return markdown_path, json_path


def _category_summaries(
    *,
    classifications: list[dict[str, Any]],
    preview_records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    preview_by_prompt = {record["prompt_id"]: record for record in preview_records}
    summaries = {
        category: {
            "record_count": 0,
            "prompt_ids": [],
            "empty_low_tier_count": 0,
            "empty_baseline_count": 0,
            "diagnostic_exact_string_match_count": 0,
            "diagnostic_exact_string_mismatch_count": 0,
            "warnings": [],
        }
        for category in CATEGORIES
    }
    for classification in classifications:
        category = classification.get("category")
        if category not in summaries:
            category = "unknown_contribution"
        prompt_id = str(classification.get("prompt_id") or "<unknown>")
        category_summary = summaries[category]
        category_summary["record_count"] += 1
        category_summary["prompt_ids"].append(prompt_id)
        category_summary["warnings"].extend(classification.get("warnings", []))
        preview = preview_by_prompt.get(prompt_id)
        if preview is None:
            continue
        if preview["low_tier_empty_after_normalization"]:
            category_summary["empty_low_tier_count"] += 1
        if preview["baseline_empty_after_normalization"]:
            category_summary["empty_baseline_count"] += 1
        if preview["normalized_outputs_exact_string_match"]:
            category_summary["diagnostic_exact_string_match_count"] += 1
        else:
            category_summary["diagnostic_exact_string_mismatch_count"] += 1
    return summaries


def _summary_warnings(
    *,
    classification_summary: dict[str, Any],
    output_health: dict[str, Any],
    prompt_mode: str | None,
) -> list[str]:
    warnings: list[str] = []
    fallback_derived_count = classification_summary["fallback_after_rejection_count"] + classification_summary["fallback_only_count"]
    total_records = classification_summary["total_records"]
    if fallback_derived_count:
        warnings.append(FALLBACK_DERIVED_WARNING)
    if total_records and fallback_derived_count > total_records / 2:
        warnings.append(MAJORITY_FALLBACK_WARNING)
    if classification_summary["unknown_contribution_count"]:
        warnings.append(UNKNOWN_CONTRIBUTION_WARNING)
    if output_health["baseline_empty_after_normalization_count"]:
        warnings.append(BASELINE_EMPTY_WARNING)
    if prompt_mode == "raw" and output_health["baseline_empty_after_normalization_count"]:
        warnings.append(RAW_PROMPT_MODE_WARNING)
    return warnings


def _trace_prompt_mode(path: Path) -> str | None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    if isinstance(records, list):
        for record in records:
            if not isinstance(record, dict):
                continue
            settings = record.get("generation_settings")
            if isinstance(settings, dict) and isinstance(settings.get("prompt_mode"), str):
                return settings["prompt_mode"]
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        settings = metadata.get("generation_settings")
        if isinstance(settings, dict) and isinstance(settings.get("prompt_mode"), str):
            return settings["prompt_mode"]
    return None


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
