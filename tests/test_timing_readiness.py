from __future__ import annotations

import json
from pathlib import Path

from htfsd.cli.run_benchmark_readiness import main as run_benchmark_readiness_main
from htfsd.metrics.environment_snapshot import build_environment_snapshot
from htfsd.metrics.timing_schema import (
    NON_CLAIMS,
    TIMING_CATEGORIES,
    RunManifest,
    TimingBoundary,
    TimingCategorySummary,
    TimingSummary,
    create_run_manifest,
)
from htfsd.metrics.timing_summary import (
    build_scaffold_timing_summary,
    render_benchmark_readiness_report,
    write_benchmark_readiness_artifacts,
)


def test_timing_schema_serializes_to_json_without_forbidden_fields() -> None:
    summary = TimingSummary(
        run_id="run-test",
        run_kind="benchmark_readiness_scaffold",
        boundaries=TimingBoundary(total_wall_time_seconds=1.25),
        category_summaries=[
            TimingCategorySummary(category="valid_draft_continuation", record_count=2, prompt_ids=["p1", "p2"])
        ],
    )

    data = summary.to_dict()
    encoded = json.dumps(data)

    assert data["boundaries"]["total_wall_time_seconds"] == 1.25
    assert data["category_summaries"][0]["category"] == "valid_draft_continuation"
    for forbidden in ("speedup", "performance_gain", "benchmark_score", "acceptance_rate"):
        assert forbidden not in encoded


def test_run_manifest_includes_required_fields() -> None:
    manifest = create_run_manifest(
        run_id="run-test",
        artifact_paths={"timing_summary": "logs/benchmark-readiness/run-test-timing-summary.json"},
        environment_snapshot={"os": "Linux", "git_commit": "abc123"},
    )

    data = manifest.to_dict()

    assert data["mvp_name"] == "Low-Tier Diagnostic MVP v0.1"
    assert data["prompt_set_id"] == "phase-2-controlled-eligibility-v2"
    assert data["prompt_count"] == 16
    assert data["prompt_mode"] == "raw"
    assert data["capture_raw_output"] is False
    assert data["artifact_paths"]["timing_summary"].endswith("timing-summary.json")
    assert data["non_claims"] == list(NON_CLAIMS)


def test_environment_snapshot_fills_unknown_instead_of_failing(monkeypatch) -> None:
    def fail_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise OSError("command unavailable")

    monkeypatch.setattr("htfsd.metrics.environment_snapshot.subprocess.run", fail_run)

    snapshot = build_environment_snapshot(
        config_path="configs/local.example.yaml",
        prompt_set_id="phase-2-controlled-eligibility-v2",
        runtime_backend="llama.cpp",
        package_names=("definitely-missing-package",),
    )

    assert snapshot["git_commit"] == "unknown"
    assert snapshot["cuda_available"] in {True, False, "unknown"}
    assert snapshot["package_versions"]["definitely-missing-package"] == "unknown"
    assert snapshot["config_path"] == "configs/local.example.yaml"


def test_timing_summary_writer_creates_expected_files(tmp_path: Path) -> None:
    manifest = create_run_manifest(
        run_id="run-test",
        artifact_paths={},
        environment_snapshot={"os": "Linux", "git_commit": "abc123"},
    )
    summary = build_scaffold_timing_summary(run_id="run-test")

    manifest_path, summary_path, report_path = write_benchmark_readiness_artifacts(
        manifest=manifest,
        summary=summary,
        output_dir=tmp_path,
    )

    assert manifest_path.exists()
    assert summary_path.exists()
    assert report_path.exists()
    assert json.loads(summary_path.read_text())["run_id"] == "run-test"
    report_text = report_path.read_text()
    assert "This is not a benchmark report." in report_text
    assert "run_manifest" in report_text
    assert "timing_summary" in report_text
    assert "benchmark_readiness_report" in report_text


def test_fallback_aware_categories_are_preserved() -> None:
    summary = build_scaffold_timing_summary(run_id="run-test")
    categories = [item.category for item in summary.category_summaries]

    assert categories == list(TIMING_CATEGORIES)
    assert "valid_draft_continuation" in categories
    assert "excluded_fallback_derived_record" in categories


def test_readiness_report_includes_non_claims() -> None:
    manifest = create_run_manifest(
        run_id="run-test",
        artifact_paths={},
        environment_snapshot={"os": "Linux", "git_commit": "abc123"},
    )
    report = render_benchmark_readiness_report(
        manifest=manifest,
        summary=build_scaffold_timing_summary(run_id="run-test"),
    )

    assert "This is not a benchmark report." in report
    assert "No speedup claim is made." in report
    assert "No high-tier implementation claim is made." in report


def test_benchmark_readiness_cli_writes_artifacts(tmp_path: Path) -> None:
    exit_code = run_benchmark_readiness_main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert list(tmp_path.glob("*-run-manifest.json"))
    assert list(tmp_path.glob("*-timing-summary.json"))
    assert list(tmp_path.glob("*-benchmark-readiness-report.md"))


def test_benchmark_readiness_cli_routes_to_low_tier_cycle_dry_run(tmp_path: Path) -> None:
    exit_code = run_benchmark_readiness_main(
        [
            "--output-dir",
            str(tmp_path),
            "--dry-run",
            "--trace-kind",
            "low-tier-cycle",
            "--prompt-set",
            "phase-2-controlled-eligibility-v2",
            "--prompt-mode",
            "raw",
            "--draft-block-size",
            "8",
            "--max-cycles",
            "4",
            "--repetitions",
            "1",
            "--fake-cycle-trace",
        ]
    )

    assert exit_code == 0
    summary_path = next(tmp_path.glob("*-timing-summary.json"))
    report_path = next(tmp_path.glob("*-benchmark-readiness-report.md"))
    summary = json.loads(summary_path.read_text())
    encoded = json.dumps(summary)

    assert summary["trace_kind"] == "low-tier-cycle"
    assert summary["dry_run"] is True
    assert summary["repetitions_requested"] == 1
    assert summary["draft_block_size"] == 8
    assert summary["max_cycles"] == 4
    assert summary["repetition_summaries"][0]["trace_records"] == 1
    assert summary["repetition_summaries"][0]["total_cycles"] == 4
    assert summary["repetition_summaries"][0]["bridge_valid_block_count"] == 4
    assert summary["repetition_summaries"][0]["cycle_fallback_count"] == 0
    assert "bridge_valid_block_count is a bridge-level structural diagnostic count only." in summary[
        "interpretation_guards"
    ]
    assert "cycle_fallback_count is a cycle-level fallback count only." in summary["interpretation_guards"]
    for forbidden in (
        "speedup",
        "performance_gain",
        "benchmark_score",
        "acceptance_rate",
        "accepted_tokens",
        "accepted_blocks",
    ):
        assert forbidden not in encoded

    report_text = report_path.read_text()
    assert "bridge_valid_block_count is a bridge-level structural diagnostic count only." in report_text
    assert "It is not accepted block count." in report_text
    assert "cycle_fallback_count is a cycle-level fallback count only." in report_text
    assert "It is not correctness evidence." in report_text


def test_low_tier_cycle_dry_run_allows_null_timing_boundaries(tmp_path: Path) -> None:
    exit_code = run_benchmark_readiness_main(
        [
            "--output-dir",
            str(tmp_path),
            "--dry-run",
            "--trace-kind",
            "low-tier-cycle",
            "--repetitions",
            "1",
            "--fake-cycle-trace",
        ]
    )

    assert exit_code == 0
    summary = json.loads(next(tmp_path.glob("*-timing-summary.json")).read_text())

    assert summary["boundaries"]["model_load_time_seconds"] is None
    assert summary["boundaries"]["diagnostic_overhead_seconds"] is None
