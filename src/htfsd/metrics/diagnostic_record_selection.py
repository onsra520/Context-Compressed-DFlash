"""Controlled diagnostic record selection for future draft-contribution inspection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Literal

from htfsd.metrics.output_diagnostic_compare import build_diagnostic_output_comparison
from htfsd.metrics.output_diagnostic_summary import (
    FALLBACK_DERIVED_CATEGORIES,
    build_fallback_aware_output_diagnostic_summary,
)
from htfsd.metrics.output_preview import DEFAULT_PREVIEW_MAX_CHARS, build_output_normalization_preview


SelectionCategory = Literal[
    "eligible_valid_draft_record",
    "excluded_fallback_derived_record",
    "excluded_unknown_contribution_record",
    "excluded_empty_baseline_record",
    "excluded_prompt_mode_risk_record",
]

FALLBACK_EXCLUSION_WARNING = (
    "This record used Gemma fallback. It is excluded from draft-contribution diagnostics."
)
FALLBACK_MATCH_WARNING = (
    "Diagnostic string matches in fallback-derived records mostly reflect Gemma fallback behavior, "
    "not successful Qwen draft contribution."
)
UNKNOWN_WARNING = "This record has unknown contribution category due to missing or contradictory fields."
EMPTY_BASELINE_WARNING = (
    "The baseline output is empty after normalization. This record is uninformative for target-baseline "
    "string diagnostics."
)
RAW_PROMPT_MODE_WARNING = (
    "Raw prompt mode may produce empty Gemma baseline outputs for this prompt set. Consider chat mode for "
    "output-comparison preparation."
)
CHAT_FALLBACK_WARNING = (
    "Chat prompt mode produced fallback-derived low-tier records in this run. Matches in this mode must "
    "not be read as Qwen draft contribution."
)
SETTINGS_MISMATCH_WARNING = (
    "Generation settings differ between traces. This record is excluded from draft-contribution diagnostics."
)


@dataclass(frozen=True)
class DiagnosticRecordSelection:
    """Selection decision for one joined diagnostic record."""

    prompt_id: str
    selection_category: SelectionCategory
    contribution_category: str
    eligible_for_draft_contribution_diagnostic: bool
    exclusion_reasons: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-friendly data."""

        return asdict(self)


@dataclass(frozen=True)
class DiagnosticRecordSelectionSummary:
    """Summary of controlled diagnostic record selection decisions."""

    total_records: int
    eligible_valid_draft_record_count: int
    excluded_fallback_derived_record_count: int
    excluded_unknown_contribution_record_count: int
    excluded_empty_baseline_record_count: int
    excluded_prompt_mode_risk_record_count: int
    eligible_prompt_ids: list[str]
    excluded_prompt_ids_by_reason: dict[str, list[str]]
    warnings: list[str]
    selections: list[DiagnosticRecordSelection]
    selection_ready: bool = True
    blocking_reasons: list[str] | None = None
    low_tier_path: str | None = None
    baseline_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-friendly data."""

        data = asdict(self)
        data["selections"] = [selection.to_dict() for selection in self.selections]
        data["blocking_reasons"] = self.blocking_reasons or []
        return data


def select_diagnostic_record(record: dict[str, Any]) -> DiagnosticRecordSelection:
    """Select or exclude one joined diagnostic record using Phase 2.8 priority rules."""

    prompt_id = str(record.get("prompt_id") or "<unknown>")
    contribution_category = str(record.get("contribution_category") or record.get("category") or "unknown_contribution")
    prompt_mode = _prompt_mode(record)
    fallback_count = _int_or_none(record.get("fallback_count"))
    draft_valid_count = _int_or_none(record.get("draft_valid_count"))
    draft_rejected_count = _int_or_none(record.get("draft_rejected_count"))
    bridge_status = record.get("bridge_status")
    baseline_empty = _baseline_empty(record)
    low_tier_empty = record.get("low_tier_empty_after_normalization") is True
    has_exact_flag = isinstance(record.get("normalized_outputs_exact_string_match"), bool)
    generation_settings_match = record.get("generation_settings_match", True) is True
    fallback_derived = (
        contribution_category in FALLBACK_DERIVED_CATEGORIES
        or (fallback_count is not None and fallback_count > 0)
        or record.get("gemma_fallback_used") is True
    )

    exclusion_reasons: list[str] = []
    warnings: list[str] = []
    missing_fields = _selection_missing_fields(
        record=record,
        prompt_id=prompt_id,
        prompt_mode=prompt_mode,
        fallback_count=fallback_count,
        draft_valid_count=draft_valid_count,
        draft_rejected_count=draft_rejected_count,
        has_exact_flag=has_exact_flag,
    )

    if contribution_category == "unknown_contribution" or record.get("missing_fields") or record.get("conflicting_fields") or missing_fields:
        exclusion_reasons.append("unknown_contribution")
        warnings.append(UNKNOWN_WARNING)
        if missing_fields:
            exclusion_reasons.append("missing_required_selection_fields")

    if fallback_derived:
        exclusion_reasons.append("fallback_derived")
        warnings.append(FALLBACK_EXCLUSION_WARNING)

    if baseline_empty:
        exclusion_reasons.append("empty_baseline")
        warnings.append(EMPTY_BASELINE_WARNING)

    if low_tier_empty:
        exclusion_reasons.append("empty_low_tier")

    if prompt_mode == "raw" and baseline_empty:
        exclusion_reasons.append("prompt_mode_risk")
        warnings.append(RAW_PROMPT_MODE_WARNING)

    if prompt_mode == "chat" and fallback_derived:
        exclusion_reasons.append("prompt_mode_risk")
        warnings.append(CHAT_FALLBACK_WARNING)

    if not generation_settings_match:
        exclusion_reasons.append("prompt_mode_risk")
        warnings.append(SETTINGS_MISMATCH_WARNING)

    exclusion_reasons = _dedupe(exclusion_reasons)
    warnings = _dedupe(warnings)
    if "unknown_contribution" in exclusion_reasons or "missing_required_selection_fields" in exclusion_reasons:
        category: SelectionCategory = "excluded_unknown_contribution_record"
    elif "fallback_derived" in exclusion_reasons:
        category = "excluded_fallback_derived_record"
    elif "empty_baseline" in exclusion_reasons:
        category = "excluded_empty_baseline_record"
    elif "prompt_mode_risk" in exclusion_reasons or "empty_low_tier" in exclusion_reasons:
        category = "excluded_prompt_mode_risk_record"
    elif _is_eligible_valid_draft(
        contribution_category=contribution_category,
        bridge_status=bridge_status,
        fallback_count=fallback_count,
        draft_valid_count=draft_valid_count,
        draft_rejected_count=draft_rejected_count,
        low_tier_empty=low_tier_empty,
        baseline_empty=baseline_empty,
        has_exact_flag=has_exact_flag,
        prompt_id=prompt_id,
        prompt_mode=prompt_mode,
    ):
        category = "eligible_valid_draft_record"
    else:
        category = "excluded_unknown_contribution_record"
        exclusion_reasons = _dedupe([*exclusion_reasons, "unknown_contribution"])
        warnings = _dedupe([*warnings, UNKNOWN_WARNING])

    return DiagnosticRecordSelection(
        prompt_id=prompt_id,
        selection_category=category,
        contribution_category=contribution_category,
        eligible_for_draft_contribution_diagnostic=category == "eligible_valid_draft_record",
        exclusion_reasons=exclusion_reasons,
        warnings=warnings,
    )


def summarize_diagnostic_record_selection(records: list[dict[str, Any]]) -> DiagnosticRecordSelectionSummary:
    """Summarize controlled diagnostic record selection decisions."""

    selections = [select_diagnostic_record(record) for record in records]
    excluded_by_reason: dict[str, list[str]] = {}
    for selection in selections:
        for reason in selection.exclusion_reasons:
            excluded_by_reason.setdefault(reason, []).append(selection.prompt_id)
    return DiagnosticRecordSelectionSummary(
        total_records=len(selections),
        eligible_valid_draft_record_count=_count(selections, "eligible_valid_draft_record"),
        excluded_fallback_derived_record_count=_count(selections, "excluded_fallback_derived_record"),
        excluded_unknown_contribution_record_count=_count(selections, "excluded_unknown_contribution_record"),
        excluded_empty_baseline_record_count=_count(selections, "excluded_empty_baseline_record"),
        excluded_prompt_mode_risk_record_count=_count(selections, "excluded_prompt_mode_risk_record"),
        eligible_prompt_ids=[selection.prompt_id for selection in selections if selection.eligible_for_draft_contribution_diagnostic],
        excluded_prompt_ids_by_reason={reason: sorted(prompt_ids) for reason, prompt_ids in sorted(excluded_by_reason.items())},
        warnings=sorted({warning for selection in selections for warning in selection.warnings}),
        selections=selections,
    )


def select_diagnostic_records_from_traces(
    *,
    low_tier_path: str | Path,
    baseline_path: str | Path,
    preview_max_chars: int = DEFAULT_PREVIEW_MAX_CHARS,
) -> DiagnosticRecordSelectionSummary:
    """Build a controlled selection summary from raw-capture low-tier and baseline traces."""

    diagnostic = build_diagnostic_output_comparison(
        low_tier_path=low_tier_path,
        baseline_path=baseline_path,
        preview_max_chars=preview_max_chars,
    )
    fallback_summary = build_fallback_aware_output_diagnostic_summary(
        low_tier_path=low_tier_path,
        baseline_path=baseline_path,
        preview_max_chars=preview_max_chars,
    )
    preview = build_output_normalization_preview(
        low_tier_path=low_tier_path,
        baseline_path=baseline_path,
        preview_max_chars=preview_max_chars,
    )
    joined = _joined_records(
        low_records=_trace_records(Path(low_tier_path)),
        classifications=fallback_summary["classification_records"],
        previews=preview["preview_records"],
        diagnostic_records=diagnostic["record_results"],
        precheck=diagnostic["precheck"],
    )
    summary = summarize_diagnostic_record_selection(joined)
    return DiagnosticRecordSelectionSummary(
        total_records=summary.total_records,
        eligible_valid_draft_record_count=summary.eligible_valid_draft_record_count,
        excluded_fallback_derived_record_count=summary.excluded_fallback_derived_record_count,
        excluded_unknown_contribution_record_count=summary.excluded_unknown_contribution_record_count,
        excluded_empty_baseline_record_count=summary.excluded_empty_baseline_record_count,
        excluded_prompt_mode_risk_record_count=summary.excluded_prompt_mode_risk_record_count,
        eligible_prompt_ids=summary.eligible_prompt_ids,
        excluded_prompt_ids_by_reason=summary.excluded_prompt_ids_by_reason,
        warnings=summary.warnings,
        selections=summary.selections,
        selection_ready=diagnostic["diagnostic_ready"],
        blocking_reasons=diagnostic["blocking_reasons"],
        low_tier_path=str(Path(low_tier_path)),
        baseline_path=str(Path(baseline_path)),
    )


def render_diagnostic_record_selection_markdown(summary: DiagnosticRecordSelectionSummary) -> str:
    """Render controlled diagnostic record selection as markdown."""

    ready = "yes" if summary.selection_ready else "no"
    lines = [
        "# Diagnostic Record Selection",
        "",
        "## Summary",
        "",
        "Controlled selector for future draft-contribution diagnostic records.",
        "",
        "## Input Files",
        "",
        f"- Low-tier: `{summary.low_tier_path}`",
        f"- Baseline: `{summary.baseline_path}`",
        "",
        "## Selection Counts",
        "",
        f"- selection_ready: {ready}",
        f"- blocking_reasons: {summary.blocking_reasons or []}",
        f"- total_records: {summary.total_records}",
        f"- eligible_valid_draft_record_count: {summary.eligible_valid_draft_record_count}",
        f"- excluded_fallback_derived_record_count: {summary.excluded_fallback_derived_record_count}",
        f"- excluded_unknown_contribution_record_count: {summary.excluded_unknown_contribution_record_count}",
        f"- excluded_empty_baseline_record_count: {summary.excluded_empty_baseline_record_count}",
        f"- excluded_prompt_mode_risk_record_count: {summary.excluded_prompt_mode_risk_record_count}",
        "",
        "## Eligible Records",
        "",
        f"- eligible_prompt_ids: {summary.eligible_prompt_ids}",
        "",
        "## Excluded Records",
        "",
    ]
    for selection in summary.selections:
        if selection.eligible_for_draft_contribution_diagnostic:
            continue
        lines.extend(
            [
                f"- {selection.prompt_id}",
                f"  - selection_category: {selection.selection_category}",
                f"  - contribution_category: {selection.contribution_category}",
                f"  - exclusion_reasons: {selection.exclusion_reasons}",
            ]
        )
    lines.extend(
        [
            "",
            "## Exclusion Reasons",
            "",
            f"- excluded_prompt_ids_by_reason: {summary.excluded_prompt_ids_by_reason}",
            "",
            "## Warnings",
            "",
            f"- warnings: {summary.warnings}",
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
            "Diagnostic record selection generated for inspection only." if summary.selection_ready else "Diagnostic record selection blocked by precheck.",
            "",
        ]
    )
    return "\n".join(lines)


def write_diagnostic_record_selection_reports(
    *,
    summary: DiagnosticRecordSelectionSummary,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """Write markdown and JSON selection reports."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-diagnostic-record-selection"
    markdown_path = _next_report_path(directory, stem, ".md")
    json_path = _next_report_path(directory, stem, ".json")
    markdown_path.write_text(render_diagnostic_record_selection_markdown(summary), encoding="utf-8")
    json_path.write_text(json.dumps(summary.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return markdown_path, json_path


def _joined_records(
    *,
    low_records: list[dict[str, Any]],
    classifications: list[dict[str, Any]],
    previews: list[dict[str, Any]],
    diagnostic_records: list[dict[str, Any]],
    precheck: dict[str, Any],
) -> list[dict[str, Any]]:
    low_by_prompt = {str(record.get("prompt_id") or "<unknown>"): record for record in low_records}
    preview_by_prompt = {record["prompt_id"]: record for record in previews}
    diagnostic_by_prompt = {record["prompt_id"]: record for record in diagnostic_records}
    records: list[dict[str, Any]] = []
    for classification in classifications:
        prompt_id = str(classification.get("prompt_id") or "<unknown>")
        low_record = low_by_prompt.get(prompt_id, {})
        preview = preview_by_prompt.get(prompt_id, {})
        diagnostic = diagnostic_by_prompt.get(prompt_id, {})
        records.append(
            {
                **low_record,
                **classification,
                **preview,
                **diagnostic,
                "contribution_category": classification.get("category", "unknown_contribution"),
                "generation_settings_match": precheck.get("generation_settings_match", False),
                "prompt_coverage_status": precheck.get("prompt_coverage_status"),
                "runtime_metadata_match": precheck.get("runtime_metadata_match"),
            }
        )
    return records


def _trace_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    return [record for record in records if isinstance(record, dict)] if isinstance(records, list) else []


def _selection_missing_fields(
    *,
    record: dict[str, Any],
    prompt_id: str,
    prompt_mode: str | None,
    fallback_count: int | None,
    draft_valid_count: int | None,
    draft_rejected_count: int | None,
    has_exact_flag: bool,
) -> list[str]:
    missing: list[str] = []
    if prompt_id == "<unknown>":
        missing.append("prompt_id")
    if not isinstance(record.get("bridge_status"), str):
        missing.append("bridge_status")
    if fallback_count is None:
        missing.append("fallback_count")
    if draft_valid_count is None:
        missing.append("draft_valid_count")
    if draft_rejected_count is None:
        missing.append("draft_rejected_count")
    if prompt_mode is None:
        missing.append("generation_settings.prompt_mode")
    if not has_exact_flag:
        missing.append("normalized_outputs_exact_string_match")
    return missing


def _is_eligible_valid_draft(
    *,
    contribution_category: str,
    bridge_status: Any,
    fallback_count: int | None,
    draft_valid_count: int | None,
    draft_rejected_count: int | None,
    low_tier_empty: bool,
    baseline_empty: bool,
    has_exact_flag: bool,
    prompt_id: str,
    prompt_mode: str | None,
) -> bool:
    return (
        contribution_category == "valid_draft_continuation"
        and bridge_status == "valid"
        and fallback_count == 0
        and draft_valid_count is not None
        and draft_valid_count > 0
        and draft_rejected_count == 0
        and not low_tier_empty
        and not baseline_empty
        and has_exact_flag
        and prompt_id != "<unknown>"
        and prompt_mode is not None
    )


def _baseline_empty(record: dict[str, Any]) -> bool:
    if record.get("baseline_empty_after_normalization") is True:
        return True
    baseline_length = _int_or_none(record.get("baseline_normalized_length"))
    if baseline_length == 0:
        return True
    if record.get("baseline_output_present") is False:
        return True
    return False


def _prompt_mode(record: dict[str, Any]) -> str | None:
    settings = record.get("generation_settings")
    if isinstance(settings, dict) and isinstance(settings.get("prompt_mode"), str):
        return settings["prompt_mode"]
    return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _count(selections: list[DiagnosticRecordSelection], category: SelectionCategory) -> int:
    return sum(1 for selection in selections if selection.selection_category == category)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


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
