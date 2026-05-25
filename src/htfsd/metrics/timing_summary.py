"""Writers for low-tier benchmark-readiness timing artifacts."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import json
from pathlib import Path

from htfsd.metrics.timing_schema import (
    DEFAULT_RUN_KIND,
    NON_CLAIMS,
    TIMING_CATEGORIES,
    RunManifest,
    TimingBoundary,
    TimingCategorySummary,
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
        "## Fallback-Aware Categories",
        "",
    ]
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
