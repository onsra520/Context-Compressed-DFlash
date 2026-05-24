"""Prepare controlled output comparison by checking trace preconditions."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from htfsd.metrics.output_compare import prepare_output_comparison_precheck, write_output_comparison_precheck_reports


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check readiness for controlled output comparison.")
    parser.add_argument("--low-tier", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--output-dir", default="logs/reports")
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = prepare_output_comparison_precheck(low_tier_path=args.low_tier, baseline_path=args.baseline)
    markdown_path, json_path = write_output_comparison_precheck_reports(result=result, output_dir=args.output_dir)
    ready = "yes" if result["output_comparison_ready"] else "no"
    print("output comparison precheck: ok")
    print(f"markdown_report: {markdown_path}")
    print(f"json_report: {json_path}")
    print(f"output_comparison_ready: {ready}")
    print(f"blocking_reasons: {result['blocking_reasons']}")
    return 0 if result["output_comparison_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
