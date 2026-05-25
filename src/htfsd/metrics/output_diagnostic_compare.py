"""Diagnostic-only output comparison summaries grouped by contribution category."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from htfsd.metrics.output_diagnostic_summary import (
    CATEGORIES,
    FALLBACK_DERIVED_CATEGORIES,
    build_fallback_aware_output_diagnostic_summary,
)
from htfsd.metrics.output_preview import DEFAULT_PREVIEW_MAX_CHARS, build_output_normalization_preview


FALLBACK_RECORD_WARNING = (
    "This record used Gemma fallback. Any diagnostic string match mostly reflects fallback behavior, "
    "not successful Qwen draft contribution."
)
FALLBACK_MATCH_WARNING = "Fallback-derived diagnostic string matches must not be interpreted as Qwen draft success."
VALID_DRAFT_MATCH_WARNING = (
    "Valid-draft diagnostic string matches are inspection metadata only. "
    "They do not prove target-equivalent generation."
)


def build_diagnostic_output_comparison(
    *,
    low_tier_path: str | Path,
    baseline_path: str | Path,
    preview_max_chars: int = DEFAULT_PREVIEW_MAX_CHARS,
) -> dict[str, Any]:
    """Build diagnostic exact-string flag summaries without making output claims."""

    summary = build_fallback_aware_output_diagnostic_summary(
        low_tier_path=low_tier_path,
        baseline_path=baseline_path,
        preview_max_chars=preview_max_chars,
    )
    preview = build_output_normalization_preview(
        low_tier_path=low_tier_path,
        baseline_path=baseline_path,
        preview_max_chars=preview_max_chars,
    )
    record_results = _record_results(
        classifications=summary["classification_records"],
        preview_records=preview["preview_records"],
    )
    category_results = summary["category_summaries"]
    diagnostic_match_count = sum(category["diagnostic_exact_string_match_count"] for category in category_results.values())
    diagnostic_mismatch_count = sum(category["diagnostic_exact_string_mismatch_count"] for category in category_results.values())
    valid_category = category_results["valid_draft_continuation"]
    fallback_matches = sum(
        category_results[category]["diagnostic_exact_string_match_count"] for category in FALLBACK_DERIVED_CATEGORIES
    )
    fallback_mismatches = sum(
        category_results[category]["diagnostic_exact_string_mismatch_count"] for category in FALLBACK_DERIVED_CATEGORIES
    )
    warnings = _diagnostic_warnings(summary=summary, fallback_matches=fallback_matches, valid_matches=valid_category["diagnostic_exact_string_match_count"])
    return {
        "low_tier_path": str(Path(low_tier_path)),
        "baseline_path": str(Path(baseline_path)),
        "diagnostic_ready": summary["summary_ready"],
        "precheck_ready": summary["precheck_ready"],
        "blocking_reasons": summary["blocking_reasons"],
        "precheck": summary["precheck"],
        "total_records": summary["total_records"],
        "valid_draft_continuation_count": summary["valid_draft_continuation_count"],
        "fallback_after_rejection_count": summary["fallback_after_rejection_count"],
        "fallback_only_count": summary["fallback_only_count"],
        "unknown_contribution_count": summary["unknown_contribution_count"],
        "diagnostic_exact_string_match_count": diagnostic_match_count,
        "diagnostic_exact_string_mismatch_count": diagnostic_mismatch_count,
        "valid_draft_diagnostic_match_count": valid_category["diagnostic_exact_string_match_count"],
        "valid_draft_diagnostic_mismatch_count": valid_category["diagnostic_exact_string_mismatch_count"],
        "fallback_derived_diagnostic_match_count": fallback_matches,
        "fallback_derived_diagnostic_mismatch_count": fallback_mismatches,
        "unknown_diagnostic_count": category_results["unknown_contribution"]["record_count"],
        "category_results": category_results,
        "record_results": record_results,
        "warnings": warnings,
        "preview_max_chars": preview_max_chars,
    }


def render_diagnostic_output_comparison_markdown(result: dict[str, Any]) -> str:
    """Render diagnostic output comparison as markdown."""

    ready = "yes" if result["diagnostic_ready"] else "no"
    lines = [
        "# Diagnostic Output Comparison",
        "",
        "## Summary",
        "",
        "Diagnostic exact-string flag summary grouped by low-tier contribution category.",
        "",
        "## Input Files",
        "",
        f"- Low-tier: `{result['low_tier_path']}`",
        f"- Baseline: `{result['baseline_path']}`",
        "",
        "## Precheck Status",
        "",
        f"- diagnostic_ready: {ready}",
        f"- precheck_ready: {'yes' if result['precheck_ready'] else 'no'}",
        f"- blocking_reasons: {result['blocking_reasons']}",
        f"- precheck: {result['precheck']}",
        "",
        "## Contribution Category Counts",
        "",
        f"- total_records: {result['total_records']}",
        f"- valid_draft_continuation_count: {result['valid_draft_continuation_count']}",
        f"- fallback_after_rejection_count: {result['fallback_after_rejection_count']}",
        f"- fallback_only_count: {result['fallback_only_count']}",
        f"- unknown_contribution_count: {result['unknown_contribution_count']}",
        "",
        "## Category-Level Diagnostic String Flags",
        "",
        f"- diagnostic_exact_string_match_count: {result['diagnostic_exact_string_match_count']}",
        f"- diagnostic_exact_string_mismatch_count: {result['diagnostic_exact_string_mismatch_count']}",
        f"- valid_draft_diagnostic_match_count: {result['valid_draft_diagnostic_match_count']}",
        f"- valid_draft_diagnostic_mismatch_count: {result['valid_draft_diagnostic_mismatch_count']}",
        f"- fallback_derived_diagnostic_match_count: {result['fallback_derived_diagnostic_match_count']}",
        f"- fallback_derived_diagnostic_mismatch_count: {result['fallback_derived_diagnostic_mismatch_count']}",
        f"- unknown_diagnostic_count: {result['unknown_diagnostic_count']}",
        "",
    ]
    for category in CATEGORIES:
        category_result = result["category_results"][category]
        lines.extend(
            [
                f"### {category}",
                "",
                f"- record_count: {category_result['record_count']}",
                f"- diagnostic_exact_string_match_count: {category_result['diagnostic_exact_string_match_count']}",
                f"- diagnostic_exact_string_mismatch_count: {category_result['diagnostic_exact_string_mismatch_count']}",
                f"- empty_low_tier_count: {category_result['empty_low_tier_count']}",
                f"- empty_baseline_count: {category_result['empty_baseline_count']}",
                f"- warnings: {category_result['warnings']}",
                "",
            ]
        )
    lines.extend(["## Record-Level Diagnostic Preview", ""])
    if result["record_results"]:
        for record in result["record_results"]:
            lines.extend(
                [
                    f"- {record['prompt_id']}",
                    f"  - category: {record['category']}",
                    f"  - normalized_outputs_exact_string_match: {record['normalized_outputs_exact_string_match']}",
                    f"  - low_tier_normalized_length: {record['low_tier_normalized_length']}",
                    f"  - baseline_normalized_length: {record['baseline_normalized_length']}",
                    f"  - warnings: {record['warnings']}",
                ]
            )
    else:
        lines.append("No record-level diagnostic preview was generated.")
    lines.extend(
        [
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
            "Diagnostic output comparison generated for inspection only." if result["diagnostic_ready"] else "Diagnostic output comparison blocked by precheck.",
            "",
        ]
    )
    return "\n".join(lines)


def write_diagnostic_output_comparison_reports(*, result: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
    """Write markdown and JSON reports."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-diagnostic-output-comparison"
    markdown_path = _next_report_path(directory, stem, ".md")
    json_path = _next_report_path(directory, stem, ".json")
    markdown_path.write_text(render_diagnostic_output_comparison_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return markdown_path, json_path


def _record_results(*, classifications: list[dict[str, Any]], preview_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preview_by_prompt = {record["prompt_id"]: record for record in preview_records}
    records: list[dict[str, Any]] = []
    for classification in classifications:
        prompt_id = str(classification.get("prompt_id") or "<unknown>")
        preview = preview_by_prompt.get(prompt_id)
        if preview is None:
            continue
        category = str(classification.get("category") or "unknown_contribution")
        records.append(
            {
                "prompt_id": prompt_id,
                "category": category,
                "normalized_outputs_exact_string_match": preview["normalized_outputs_exact_string_match"],
                "low_tier_normalized_length": preview["low_tier_normalized_length"],
                "baseline_normalized_length": preview["baseline_normalized_length"],
                "warnings": _record_warnings(
                    category=category,
                    diagnostic_match=preview["normalized_outputs_exact_string_match"],
                ),
            }
        )
    return records


def _record_warnings(*, category: str, diagnostic_match: bool) -> list[str]:
    warnings: list[str] = []
    if category in FALLBACK_DERIVED_CATEGORIES:
        warnings.append(FALLBACK_RECORD_WARNING)
    if category == "valid_draft_continuation" and diagnostic_match:
        warnings.append(VALID_DRAFT_MATCH_WARNING)
    return warnings


def _diagnostic_warnings(*, summary: dict[str, Any], fallback_matches: int, valid_matches: int) -> list[str]:
    warnings = list(summary["warnings"])
    if fallback_matches:
        warnings.append(FALLBACK_MATCH_WARNING)
    if valid_matches:
        warnings.append(VALID_DRAFT_MATCH_WARNING)
    return warnings


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
