"""Classify low-tier trace records by contribution behavior."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from htfsd.metrics.output_diagnostics import classify_low_tier_trace_file, write_low_tier_classification_markdown


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify low-tier trace records by fallback-aware contribution behavior.")
    parser.add_argument("trace_file")
    parser.add_argument("--output-dir", default="logs/reports")
    args = parser.parse_args(list(argv) if argv is not None else None)

    summary = classify_low_tier_trace_file(args.trace_file)
    report_path = write_low_tier_classification_markdown(summary=summary, output_dir=args.output_dir)
    print("low-tier classification: ok")
    print(f"report_file: {report_path}")
    print(f"total_records: {summary.total_records}")
    print(f"valid_draft_continuation_count: {summary.valid_draft_continuation_count}")
    print(f"fallback_after_rejection_count: {summary.fallback_after_rejection_count}")
    print(f"fallback_only_count: {summary.fallback_only_count}")
    print(f"unknown_contribution_count: {summary.unknown_contribution_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
