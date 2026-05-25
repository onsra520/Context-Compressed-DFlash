"""Write low-tier benchmark-readiness scaffold artifacts."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from htfsd.metrics.environment_snapshot import build_environment_snapshot
from htfsd.metrics.timing_schema import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_RUNTIME_BACKEND,
    create_run_manifest,
)
from htfsd.metrics.timing_summary import (
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
    args = parser.parse_args(list(argv) if argv is not None else None)

    run_id = args.run_id or make_run_id()
    prompt_set_id = "phase-2-controlled-eligibility-v2"
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
    summary = build_scaffold_timing_summary(run_id=run_id)
    manifest_path, summary_path, report_path = write_benchmark_readiness_artifacts(
        manifest=manifest,
        summary=summary,
        output_dir=args.output_dir,
    )
    print("benchmark readiness scaffold: ok")
    print(f"run_id: {run_id}")
    print(f"run_manifest: {manifest_path}")
    print(f"timing_summary: {summary_path}")
    print(f"readiness_report: {report_path}")
    print("benchmark_claims: none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
