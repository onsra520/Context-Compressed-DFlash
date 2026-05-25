"""Write compact eligible-record inspection reports."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from htfsd.metrics.eligible_record_inspection import (
    DEFAULT_PREVIEW_MAX_CHARS,
    build_eligible_record_inspection,
    write_eligible_record_inspection_reports,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write an eligible-record inspection report.")
    parser.add_argument("--low-tier", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--output-dir", default="logs/reports")
    parser.add_argument("--preview-max-chars", type=int, default=DEFAULT_PREVIEW_MAX_CHARS)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = build_eligible_record_inspection(
        low_tier_path=args.low_tier,
        baseline_path=args.baseline,
        preview_max_chars=args.preview_max_chars,
    )
    markdown_path, json_path = write_eligible_record_inspection_reports(result=result, output_dir=args.output_dir)
    selector_status = result["selector_status"]
    ready = "yes" if result["inspection_ready"] else "no"
    print("eligible record inspection: ok")
    print(f"markdown_report: {markdown_path}")
    print(f"json_report: {json_path}")
    print(f"inspection_ready: {ready}")
    print(f"eligible_record_count: {result['eligible_record_count']}")
    print(f"excluded_fallback_derived_record_count: {selector_status['excluded_fallback_derived_record_count']}")
    print(f"excluded_unknown_contribution_record_count: {selector_status['excluded_unknown_contribution_record_count']}")
    print(f"excluded_empty_baseline_record_count: {selector_status['excluded_empty_baseline_record_count']}")
    print(f"excluded_prompt_mode_risk_record_count: {selector_status['excluded_prompt_mode_risk_record_count']}")
    print(f"blocking_reasons: {result['blocking_reasons']}")
    return 0 if result["inspection_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
