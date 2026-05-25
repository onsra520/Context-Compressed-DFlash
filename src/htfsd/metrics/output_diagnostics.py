"""Fallback-aware low-tier output diagnostic classification."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Literal


ContributionCategory = Literal[
    "valid_draft_continuation",
    "fallback_after_rejection",
    "fallback_only",
    "unknown_contribution",
]

REQUIRED_CLASSIFICATION_FIELDS = (
    "bridge_status",
    "rejection_reason",
    "fallback_count",
    "draft_valid_count",
    "draft_rejected_count",
    "generation_settings.prompt_mode",
)

FALLBACK_WARNING = (
    "This record used Gemma fallback. Any string match mostly reflects fallback behavior, "
    "not successful draft contribution."
)


@dataclass(frozen=True)
class DiagnosticClassification:
    """Classification result for one low-tier trace record."""

    prompt_id: str
    category: ContributionCategory
    bridge_status: str | None
    fallback_count: int | None
    rejection_reason: str | None
    missing_fields: list[str]
    conflicting_fields: list[str]
    warnings: list[str]
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-friendly data."""

        return asdict(self)


@dataclass(frozen=True)
class DiagnosticClassificationSummary:
    """Summary of low-tier contribution classifications."""

    total_records: int
    valid_draft_continuation_count: int
    fallback_after_rejection_count: int
    fallback_only_count: int
    unknown_contribution_count: int
    unknown_record_ids: list[str]
    missing_fields_by_record: dict[str, list[str]]
    conflicting_fields_by_record: dict[str, list[str]]
    warnings: list[str]
    classifications: list[DiagnosticClassification]
    input_trace: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-friendly data."""

        data = asdict(self)
        data["classifications"] = [classification.to_dict() for classification in self.classifications]
        return data


def classify_low_tier_record(record: dict[str, Any]) -> DiagnosticClassification:
    """Classify one low-tier trace record by contribution behavior."""

    prompt_id = str(record.get("prompt_id") or "<unknown>")
    bridge_status = record.get("bridge_status") if isinstance(record.get("bridge_status"), str) else None
    rejection_reason = record.get("rejection_reason") if isinstance(record.get("rejection_reason"), str) else None
    fallback_count = _int_or_none(record.get("fallback_count"))
    draft_valid_count = _int_or_none(record.get("draft_valid_count"))
    draft_rejected_count = _int_or_none(record.get("draft_rejected_count"))
    prompt_mode = _prompt_mode(record)

    missing_fields = _missing_fields(
        record=record,
        bridge_status=bridge_status,
        fallback_count=fallback_count,
        draft_valid_count=draft_valid_count,
        draft_rejected_count=draft_rejected_count,
        prompt_mode=prompt_mode,
    )
    conflicting_fields = _conflicting_fields(
        bridge_status=bridge_status,
        fallback_count=fallback_count,
        draft_valid_count=draft_valid_count,
        draft_rejected_count=draft_rejected_count,
        gemma_fallback_used=record.get("gemma_fallback_used"),
    )
    if missing_fields:
        return DiagnosticClassification(
            prompt_id=prompt_id,
            category="unknown_contribution",
            bridge_status=bridge_status,
            fallback_count=fallback_count,
            rejection_reason=rejection_reason,
            missing_fields=missing_fields,
            conflicting_fields=conflicting_fields,
            warnings=[],
            reason="missing_required_fields",
        )
    if conflicting_fields:
        return DiagnosticClassification(
            prompt_id=prompt_id,
            category="unknown_contribution",
            bridge_status=bridge_status,
            fallback_count=fallback_count,
            rejection_reason=rejection_reason,
            missing_fields=missing_fields,
            conflicting_fields=conflicting_fields,
            warnings=[],
            reason="conflicting_classification_fields",
        )

    assert fallback_count is not None
    assert draft_valid_count is not None
    assert draft_rejected_count is not None

    if (
        bridge_status == "valid"
        and fallback_count == 0
        and draft_valid_count > 0
        and draft_rejected_count == 0
        and record.get("gemma_fallback_used") is not True
    ):
        return DiagnosticClassification(
            prompt_id=prompt_id,
            category="valid_draft_continuation",
            bridge_status=bridge_status,
            fallback_count=fallback_count,
            rejection_reason=rejection_reason,
            missing_fields=[],
            conflicting_fields=[],
            warnings=[],
        )

    if bridge_status == "rejected" and fallback_count > 0 and draft_rejected_count > 0 and rejection_reason:
        return DiagnosticClassification(
            prompt_id=prompt_id,
            category="fallback_after_rejection",
            bridge_status=bridge_status,
            fallback_count=fallback_count,
            rejection_reason=rejection_reason,
            missing_fields=[],
            conflicting_fields=[],
            warnings=[FALLBACK_WARNING],
        )

    if fallback_count > 0:
        return DiagnosticClassification(
            prompt_id=prompt_id,
            category="fallback_only",
            bridge_status=bridge_status,
            fallback_count=fallback_count,
            rejection_reason=rejection_reason,
            missing_fields=[],
            conflicting_fields=[],
            warnings=[FALLBACK_WARNING],
            reason="incomplete_rejection_metadata",
        )

    return DiagnosticClassification(
        prompt_id=prompt_id,
        category="unknown_contribution",
        bridge_status=bridge_status,
        fallback_count=fallback_count,
        rejection_reason=rejection_reason,
        missing_fields=[],
        conflicting_fields=["classification_rules_not_satisfied"],
        warnings=[],
        reason="classification_rules_not_satisfied",
    )


def summarize_low_tier_classifications(records: list[dict[str, Any]]) -> DiagnosticClassificationSummary:
    """Summarize low-tier record contribution categories."""

    classifications = [classify_low_tier_record(record) for record in records]
    missing_by_record = {
        classification.prompt_id: classification.missing_fields
        for classification in classifications
        if classification.missing_fields
    }
    conflicting_by_record = {
        classification.prompt_id: classification.conflicting_fields
        for classification in classifications
        if classification.conflicting_fields
    }
    warnings = sorted({warning for classification in classifications for warning in classification.warnings})
    return DiagnosticClassificationSummary(
        total_records=len(classifications),
        valid_draft_continuation_count=_count(classifications, "valid_draft_continuation"),
        fallback_after_rejection_count=_count(classifications, "fallback_after_rejection"),
        fallback_only_count=_count(classifications, "fallback_only"),
        unknown_contribution_count=_count(classifications, "unknown_contribution"),
        unknown_record_ids=[classification.prompt_id for classification in classifications if classification.category == "unknown_contribution"],
        missing_fields_by_record=missing_by_record,
        conflicting_fields_by_record=conflicting_by_record,
        warnings=warnings,
        classifications=classifications,
    )


def classify_low_tier_trace_file(path: str | Path) -> DiagnosticClassificationSummary:
    """Classify all records in a low-tier trace JSON file."""

    trace_path = Path(path)
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    if not isinstance(records, list):
        records = []
    summary = summarize_low_tier_classifications([record for record in records if isinstance(record, dict)])
    return DiagnosticClassificationSummary(
        total_records=summary.total_records,
        valid_draft_continuation_count=summary.valid_draft_continuation_count,
        fallback_after_rejection_count=summary.fallback_after_rejection_count,
        fallback_only_count=summary.fallback_only_count,
        unknown_contribution_count=summary.unknown_contribution_count,
        unknown_record_ids=summary.unknown_record_ids,
        missing_fields_by_record=summary.missing_fields_by_record,
        conflicting_fields_by_record=summary.conflicting_fields_by_record,
        warnings=summary.warnings,
        classifications=summary.classifications,
        input_trace=str(trace_path),
    )


def render_low_tier_classification_markdown(summary: DiagnosticClassificationSummary) -> str:
    """Render a compact markdown classification report."""

    lines = [
        "# Low-Tier Contribution Classification",
        "",
        "## Summary",
        "",
        "Fallback-aware classification for low-tier trace records.",
        "",
        "## Input Trace",
        "",
        f"- input_trace: `{summary.input_trace}`",
        "",
        "## Category Counts",
        "",
        f"- total_records: {summary.total_records}",
        f"- valid_draft_continuation_count: {summary.valid_draft_continuation_count}",
        f"- fallback_after_rejection_count: {summary.fallback_after_rejection_count}",
        f"- fallback_only_count: {summary.fallback_only_count}",
        f"- unknown_contribution_count: {summary.unknown_contribution_count}",
        "",
        "## Record Classifications",
        "",
    ]
    for classification in summary.classifications:
        lines.extend(
            [
                f"- {classification.prompt_id}: {classification.category}",
                f"  - bridge_status: {classification.bridge_status}",
                f"  - fallback_count: {classification.fallback_count}",
                f"  - rejection_reason: {classification.rejection_reason}",
            ]
        )
    lines.extend(
        [
            "",
            "## Missing Fields",
            "",
            f"- missing_fields_by_record: {summary.missing_fields_by_record}",
            "",
            "## Conflicting Fields",
            "",
            f"- conflicting_fields_by_record: {summary.conflicting_fields_by_record}",
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
            "Classification completed for low-tier contribution behavior only.",
            "",
        ]
    )
    return "\n".join(lines)


def write_low_tier_classification_markdown(*, summary: DiagnosticClassificationSummary, output_dir: str | Path) -> Path:
    """Write a markdown classification report."""

    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    stem = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-low-tier-classification"
    report_path = _next_report_path(path, stem)
    report_path.write_text(render_low_tier_classification_markdown(summary), encoding="utf-8")
    return report_path


def _missing_fields(
    *,
    record: dict[str, Any],
    bridge_status: str | None,
    fallback_count: int | None,
    draft_valid_count: int | None,
    draft_rejected_count: int | None,
    prompt_mode: str | None,
) -> list[str]:
    missing: list[str] = []
    if bridge_status is None:
        missing.append("bridge_status")
    if "rejection_reason" not in record:
        missing.append("rejection_reason")
    if fallback_count is None:
        missing.append("fallback_count")
    if draft_valid_count is None:
        missing.append("draft_valid_count")
    if draft_rejected_count is None:
        missing.append("draft_rejected_count")
    if prompt_mode is None:
        missing.append("generation_settings.prompt_mode")
    return missing


def _conflicting_fields(
    *,
    bridge_status: str | None,
    fallback_count: int | None,
    draft_valid_count: int | None,
    draft_rejected_count: int | None,
    gemma_fallback_used: Any,
) -> list[str]:
    conflicts: list[str] = []
    if bridge_status == "valid" and fallback_count is not None and fallback_count > 0:
        conflicts.append("bridge_status_valid_with_fallback_count")
    if bridge_status == "rejected" and fallback_count == 0:
        conflicts.append("bridge_status_rejected_without_fallback_count")
    if gemma_fallback_used is False and fallback_count is not None and fallback_count > 0:
        conflicts.append("gemma_fallback_used_false_with_fallback_count")
    if draft_valid_count is not None and draft_rejected_count is not None and draft_valid_count > 0 and draft_rejected_count > 0:
        conflicts.append("draft_valid_and_rejected_counts_both_positive")
    return conflicts


def _prompt_mode(record: dict[str, Any]) -> str | None:
    settings = record.get("generation_settings")
    if not isinstance(settings, dict):
        return None
    prompt_mode = settings.get("prompt_mode")
    return prompt_mode if isinstance(prompt_mode, str) and prompt_mode else None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _count(classifications: list[DiagnosticClassification], category: ContributionCategory) -> int:
    return sum(1 for classification in classifications if classification.category == category)


def _next_report_path(directory: Path, stem: str) -> Path:
    path = directory / f"{stem}.md"
    if not path.exists():
        return path
    index = 2
    while True:
        candidate = directory / f"{stem}-{index}.md"
        if not candidate.exists():
            return candidate
        index += 1
