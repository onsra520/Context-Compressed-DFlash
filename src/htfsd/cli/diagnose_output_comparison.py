"""Write diagnostic-only output comparison reports."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from htfsd.metrics.output_diagnostic_compare import (
    DEFAULT_PREVIEW_MAX_CHARS,
    build_diagnostic_output_comparison,
    write_diagnostic_output_comparison_reports,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a diagnostic-only output comparison report.")
    parser.add_argument("--low-tier", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--output-dir", default="logs/reports")
    parser.add_argument("--preview-max-chars", type=int, default=DEFAULT_PREVIEW_MAX_CHARS)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = build_diagnostic_output_comparison(
        low_tier_path=args.low_tier,
        baseline_path=args.baseline,
        preview_max_chars=args.preview_max_chars,
    )
    markdown_path, json_path = write_diagnostic_output_comparison_reports(result=result, output_dir=args.output_dir)
    ready = "yes" if result["diagnostic_ready"] else "no"
    print("diagnostic output comparison: ok")
    print(f"markdown_report: {markdown_path}")
    print(f"json_report: {json_path}")
    print(f"diagnostic_ready: {ready}")
    print(f"total_records: {result['total_records']}")
    print(f"diagnostic_exact_string_match_count: {result['diagnostic_exact_string_match_count']}")
    print(f"diagnostic_exact_string_mismatch_count: {result['diagnostic_exact_string_mismatch_count']}")
    print(f"valid_draft_diagnostic_match_count: {result['valid_draft_diagnostic_match_count']}")
    print(f"fallback_derived_diagnostic_match_count: {result['fallback_derived_diagnostic_match_count']}")
    print(f"unknown_diagnostic_count: {result['unknown_diagnostic_count']}")
    print(f"blocking_reasons: {result['blocking_reasons']}")
    return 0 if result["diagnostic_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
