"""Writers for low-tier benchmark-readiness timing artifacts."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import json
from pathlib import Path

from htfsd.metrics.timing_schema import (
    BLOCK_CYCLE_INTERPRETATION_GUARDS,
    BLOCK_CYCLE_TIMING_CATEGORIES,
    DEFAULT_RUN_KIND,
    NON_CLAIMS,
    TIMING_CATEGORIES,
    RunManifest,
    TimingBoundary,
    TimingCategorySummary,
    TimingRepetitionSummary,
    TimingSummary,
)


def build_scaffold_timing_summary(*, run_id: str) -> TimingSummary:
    """Build a scaffold timing summary with category placeholders and no measured claims."""

    return TimingSummary(
        run_id=run_id,
        run_kind=DEFAULT_RUN_KIND,
        boundaries=TimingBoundary(),
        category_summaries=[
            TimingCategorySummary(
                category=category,
                warnings=[],
            )
            for category in TIMING_CATEGORIES
        ],
    )


def build_low_tier_cycle_dry_run_timing_summary(
    *,
    run_id: str,
    repetitions_requested: int,
    prompt_set_id: str,
    prompt_count: int,
    prompt_mode: str,
    draft_block_size: int,
    max_cycles: int,
    capture_raw_output: bool,
    repetition_summaries: list[TimingRepetitionSummary],
) -> TimingSummary:
    """Build a no-claim timing-readiness dry-run summary for low-tier cycle traces."""

    total_wall_times = [
        summary.total_wall_time_seconds
        for summary in repetition_summaries
        if summary.total_wall_time_seconds is not None
    ]
    total_wall_time = sum(total_wall_times) if total_wall_times else None
    bridge_valid_total = sum(summary.bridge_valid_block_count for summary in repetition_summaries)
    bridge_rejected_total = sum(summary.bridge_rejected_block_count for summary in repetition_summaries)
    fallback_total = sum(summary.cycle_fallback_count for summary in repetition_summaries)
    total_cycles = sum(summary.total_cycles for summary in repetition_summaries)
    cycle_no_fallback_count = max(total_cycles - fallback_total, 0)
    category_counts = {
        "bridge_valid_block": bridge_valid_total,
        "bridge_rejected_block": bridge_rejected_total,
        "cycle_fallback": fallback_total,
        "cycle_no_fallback": cycle_no_fallback_count,
    }
    category_summaries = [
        TimingCategorySummary(category=category, record_count=category_counts.get(category, 0))
        for category in BLOCK_CYCLE_TIMING_CATEGORIES + TIMING_CATEGORIES
    ]
    return TimingSummary(
        run_id=run_id,
        run_kind="benchmark_readiness_dry_run",
        boundaries=TimingBoundary(
            total_wall_time_seconds=total_wall_time,
        ),
        category_summaries=category_summaries,
        latency_seconds_descriptive=total_wall_time,
        trace_kind="low-tier-cycle",
        dry_run=True,
        repetitions_requested=repetitions_requested,
        prompt_set_id=prompt_set_id,
        prompt_count=prompt_count,
        prompt_mode=prompt_mode,
        draft_block_size=draft_block_size,
        max_cycles=max_cycles,
        capture_raw_output=capture_raw_output,
        cycle_trace_artifact_paths=[
            summary.cycle_trace_path for summary in repetition_summaries if summary.cycle_trace_path
        ],
        repetition_summaries=repetition_summaries,
        interpretation_guards=list(BLOCK_CYCLE_INTERPRETATION_GUARDS),
    )


def write_benchmark_readiness_artifacts(
    *,
    manifest: RunManifest,
    summary: TimingSummary,
    output_dir: str | Path,
) -> tuple[Path, Path, Path]:
    """Write manifest, summary, and markdown readiness report."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stem = manifest.run_id
    manifest_path = directory / f"{stem}-run-manifest.json"
    summary_path = directory / f"{stem}-timing-summary.json"
    report_path = directory / f"{stem}-benchmark-readiness-report.md"
    manifest_data = manifest.to_dict()
    artifact_paths = {
        "run_manifest": str(manifest_path),
        "timing_summary": str(summary_path),
        "benchmark_readiness_report": str(report_path),
    }
    manifest_data["artifact_paths"] = artifact_paths
    manifest_for_report = replace(manifest, artifact_paths=artifact_paths)
    manifest_path.write_text(json.dumps(manifest_data, indent=2, sort_keys=True), encoding="utf-8")
    summary_path.write_text(json.dumps(summary.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(render_benchmark_readiness_report(manifest=manifest_for_report, summary=summary), encoding="utf-8")
    return manifest_path, summary_path, report_path


def render_benchmark_readiness_report(*, manifest: RunManifest, summary: TimingSummary) -> str:
    """Render a no-claim benchmark-readiness scaffold report."""

    lines = [
        "# Low-Tier Benchmark Readiness Report",
        "",
        "## Summary",
        "",
        "This report records scaffold-level timing-readiness metadata only.",
        "",
        "## Run Manifest",
        "",
        f"- run_id: `{manifest.run_id}`",
        f"- run_kind: `{manifest.run_kind}`",
        f"- trace_kind: `{summary.trace_kind or 'scaffold'}`",
        f"- dry_run: {summary.dry_run}",
        f"- mvp_name: `{manifest.mvp_name}`",
        f"- prompt_set_id: `{manifest.prompt_set_id}`",
        f"- prompt_count: {manifest.prompt_count}",
        f"- prompt_mode: `{manifest.prompt_mode}`",
        f"- capture_raw_output: {manifest.capture_raw_output}",
        "",
        "## Timing Boundaries",
        "",
        "```json",
        json.dumps(summary.boundaries.to_dict(), indent=2, sort_keys=True),
        "```",
        "",
        "## Dry-Run Repetitions",
        "",
    ]
    if summary.repetition_summaries:
        for repetition in summary.repetition_summaries:
            lines.extend(
                [
                    f"- {repetition.repetition_id}:",
                    f"  - trace_kind: `{repetition.trace_kind}`",
                    f"  - cycle_trace_path: `{repetition.cycle_trace_path}`",
                    f"  - trace_records: {repetition.trace_records}",
                    f"  - total_cycles: {repetition.total_cycles}",
                    f"  - bridge_valid_block_count: {repetition.bridge_valid_block_count}",
                    f"  - bridge_rejected_block_count: {repetition.bridge_rejected_block_count}",
                    f"  - cycle_fallback_count: {repetition.cycle_fallback_count}",
                    f"  - total_wall_time_seconds: {repetition.total_wall_time_seconds}",
                ]
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Fallback-Aware Categories",
            "",
        ]
    )
    for category in summary.category_summaries:
        lines.append(f"- {category.category}: {category.record_count}")
    lines.extend(
        [
            "",
            "## Artifact Paths",
            "",
        ]
    )
    for key, value in manifest.artifact_paths.items():
        lines.append(f"- {key}: `{value}`")
    if summary.cycle_trace_artifact_paths:
        lines.extend(["", "## Cycle Trace Artifacts", ""])
        for path in summary.cycle_trace_artifact_paths:
            lines.append(f"- `{path}`")
    if summary.interpretation_guards:
        lines.extend(["", "## Interpretation Guards", ""])
        lines.extend(summary.interpretation_guards)
    lines.extend(
        [
            "",
            "## Non-Claims",
            "",
            *NON_CLAIMS,
            "",
            "## Conclusion",
            "",
            "Timing-readiness scaffold artifacts were written. Missing measured boundaries remain null until a later dry-run phase records them.",
            "",
        ]
    )
    return "\n".join(lines)


def make_run_id() -> str:
    """Return a timestamp run id for readiness artifacts."""

    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
