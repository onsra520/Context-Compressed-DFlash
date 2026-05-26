"""Write low-tier benchmark-readiness scaffold artifacts."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import sys
import time
from typing import Sequence

from htfsd.cli.run_low_tier_cycle_trace import main as run_low_tier_cycle_trace_main
from htfsd.metrics.environment_snapshot import build_environment_snapshot
from htfsd.metrics.prompt_sets import get_trace_prompt_set, trace_prompt_set_ids
from htfsd.metrics.timing_schema import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_RUNTIME_BACKEND,
    TimingRepetitionSummary,
    create_run_manifest,
)
from htfsd.metrics.timing_summary import (
    build_low_tier_cycle_dry_run_timing_summary,
    build_scaffold_timing_summary,
    make_run_id,
    write_benchmark_readiness_artifacts,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write benchmark-readiness scaffold artifacts.")
    parser.add_argument("--output-dir", default="logs/benchmark-readiness")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--runtime-backend", default=DEFAULT_RUNTIME_BACKEND)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--trace-kind", choices=("scaffold", "low-tier-cycle"), default="scaffold")
    parser.add_argument("--prompt-set", default="phase-2-controlled-eligibility-v2", choices=trace_prompt_set_ids())
    parser.add_argument("--prompt-mode", choices=("raw", "chat"), default="raw")
    parser.add_argument("--draft-block-size", type=int, default=8)
    parser.add_argument("--max-cycles", type=int, default=4)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--capture-raw-output", action="store_true")
    parser.add_argument("--fake-cycle-trace", action="store_true", help="Use fake cycle trace backends for tests.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    run_id = args.run_id or make_run_id()
    prompt_set_id = args.prompt_set
    environment_snapshot = build_environment_snapshot(
        config_path=args.config,
        prompt_set_id=prompt_set_id,
        runtime_backend=args.runtime_backend,
    )
    manifest = create_run_manifest(
        run_id=run_id,
        artifact_paths={},
        environment_snapshot=environment_snapshot,
        config_path=args.config,
        runtime_backend=args.runtime_backend,
    )
    manifest = replace(
        manifest,
        run_kind="benchmark_readiness_dry_run" if args.dry_run else manifest.run_kind,
        prompt_set_id=prompt_set_id,
        prompt_count=len(get_trace_prompt_set(prompt_set_id).prompts),
        prompt_mode=args.prompt_mode,
        capture_raw_output=args.capture_raw_output,
    )
    if args.dry_run and args.trace_kind == "low-tier-cycle":
        summary = _run_low_tier_cycle_dry_run(
            run_id=run_id,
            output_dir=Path(args.output_dir),
            config_path=args.config,
            prompt_set_id=prompt_set_id,
            prompt_mode=args.prompt_mode,
            draft_block_size=args.draft_block_size,
            max_cycles=args.max_cycles,
            repetitions=args.repetitions,
            capture_raw_output=args.capture_raw_output,
            fake_cycle_trace=args.fake_cycle_trace,
        )
    else:
        summary = build_scaffold_timing_summary(run_id=run_id)
    manifest_path, summary_path, report_path = write_benchmark_readiness_artifacts(
        manifest=manifest,
        summary=summary,
        output_dir=args.output_dir,
    )
    print("benchmark readiness scaffold: ok")
    print(f"run_id: {run_id}")
    print(f"trace_kind: {summary.trace_kind or args.trace_kind}")
    print(f"dry_run: {summary.dry_run}")
    print(f"run_manifest: {manifest_path}")
    print(f"timing_summary: {summary_path}")
    print(f"readiness_report: {report_path}")
    print("benchmark_claims: none")
    return 0


def _run_low_tier_cycle_dry_run(
    *,
    run_id: str,
    output_dir: Path,
    config_path: str,
    prompt_set_id: str,
    prompt_mode: str,
    draft_block_size: int,
    max_cycles: int,
    repetitions: int,
    capture_raw_output: bool,
    fake_cycle_trace: bool,
):
    repetition_dir = output_dir / "repetitions"
    repetition_dir.mkdir(parents=True, exist_ok=True)
    raw_trace_dir = repetition_dir / "_raw"
    raw_trace_dir.mkdir(parents=True, exist_ok=True)
    repetition_summaries: list[TimingRepetitionSummary] = []
    for index in range(1, repetitions + 1):
        repetition_id = f"rep-{index:03d}"
        started_at_utc = _utc_now()
        start = time.perf_counter()
        before = set(raw_trace_dir.glob("*-low-tier-cycle-trace.json"))
        trace_args = [
            "--config",
            config_path,
            "--prompt-set",
            prompt_set_id,
            "--prompt-mode",
            prompt_mode,
            "--draft-block-size",
            str(draft_block_size),
            "--max-cycles",
            str(max_cycles),
            "--output-dir",
            str(raw_trace_dir),
        ]
        if capture_raw_output:
            trace_args.append("--capture-raw-output")
        if fake_cycle_trace:
            trace_args.extend(["--fake", "--prompt", "A short readiness reply is"])
        exit_code = run_low_tier_cycle_trace_main(trace_args)
        ended_at_utc = _utc_now()
        total_wall_time = time.perf_counter() - start
        if exit_code != 0:
            raise RuntimeError(f"low-tier cycle dry-run repetition {repetition_id} failed")
        cycle_trace_path = _newest_trace_path(raw_trace_dir, before)
        stable_trace_path = repetition_dir / f"{run_id}-{repetition_id}-low-tier-cycle-trace.json"
        shutil.copy2(cycle_trace_path, stable_trace_path)
        counts = _cycle_trace_counts(stable_trace_path)
        repetition_summaries.append(
            TimingRepetitionSummary(
                repetition_id=repetition_id,
                trace_kind="low-tier-cycle",
                cycle_trace_path=str(stable_trace_path),
                started_at_utc=started_at_utc,
                ended_at_utc=ended_at_utc,
                total_wall_time_seconds=total_wall_time,
                generation_time_seconds=None,
                diagnostic_overhead_seconds=None,
                trace_records=counts["trace_records"],
                total_cycles=counts["total_cycles"],
                bridge_valid_block_count=counts["bridge_valid_block_count"],
                bridge_rejected_block_count=counts["bridge_rejected_block_count"],
                cycle_fallback_count=counts["cycle_fallback_count"],
            )
        )
    prompt_set = get_trace_prompt_set(prompt_set_id)
    return build_low_tier_cycle_dry_run_timing_summary(
        run_id=run_id,
        repetitions_requested=repetitions,
        prompt_set_id=prompt_set_id,
        prompt_count=len(prompt_set.prompts),
        prompt_mode=prompt_mode,
        draft_block_size=draft_block_size,
        max_cycles=max_cycles,
        capture_raw_output=capture_raw_output,
        repetition_summaries=repetition_summaries,
    )


def _newest_trace_path(directory: Path, before: set[Path]) -> Path:
    after = set(directory.glob("*-low-tier-cycle-trace.json"))
    new_paths = sorted(after - before, key=lambda path: path.stat().st_mtime)
    if not new_paths:
        raise RuntimeError("low-tier cycle trace did not produce an artifact")
    return new_paths[-1]


def _cycle_trace_counts(path: Path) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    return {
        "trace_records": len(records),
        "total_cycles": sum(int(record.get("total_cycles") or 0) for record in records),
        "bridge_valid_block_count": sum(int(record.get("bridge_valid_block_count") or 0) for record in records),
        "bridge_rejected_block_count": sum(int(record.get("bridge_rejected_block_count") or 0) for record in records),
        "cycle_fallback_count": sum(int(record.get("cycle_fallback_count") or 0) for record in records),
    }


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    sys.exit(main())
