"""Summarize output diagnostics by low-tier contribution category."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from htfsd.metrics.output_diagnostic_summary import (
    DEFAULT_PREVIEW_MAX_CHARS,
    build_fallback_aware_output_diagnostic_summary,
    write_fallback_aware_output_diagnostic_summary_reports,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a fallback-aware output diagnostic summary report.")
    parser.add_argument("--low-tier", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--output-dir", default="logs/reports")
    parser.add_argument("--preview-max-chars", type=int, default=DEFAULT_PREVIEW_MAX_CHARS)
    args = parser.parse_args(list(argv) if argv is not None else None)

    summary = build_fallback_aware_output_diagnostic_summary(
        low_tier_path=args.low_tier,
        baseline_path=args.baseline,
        preview_max_chars=args.preview_max_chars,
    )
    markdown_path, json_path = write_fallback_aware_output_diagnostic_summary_reports(
        summary=summary,
        output_dir=args.output_dir,
    )
    ready = "yes" if summary["summary_ready"] else "no"
    print("fallback-aware output diagnostic summary: ok")
    print(f"markdown_report: {markdown_path}")
    print(f"json_report: {json_path}")
    print(f"summary_ready: {ready}")
    print(f"total_records: {summary['total_records']}")
    print(f"valid_draft_continuation_count: {summary['valid_draft_continuation_count']}")
    print(f"fallback_after_rejection_count: {summary['fallback_after_rejection_count']}")
    print(f"fallback_only_count: {summary['fallback_only_count']}")
    print(f"unknown_contribution_count: {summary['unknown_contribution_count']}")
    print(f"blocking_reasons: {summary['blocking_reasons']}")
    return 0 if summary["summary_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
