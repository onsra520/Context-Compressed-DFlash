"""Generate descriptive trace comparison reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from htfsd.metrics.trace_compare import compare_trace_files, write_trace_comparison_markdown


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a descriptive trace comparison report.")
    parser.add_argument("--low-tier", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--output-dir", default="logs/reports")
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = compare_trace_files(low_tier_path=args.low_tier, baseline_path=args.baseline)
    report_path = write_trace_comparison_markdown(result=result, output_dir=args.output_dir)
    print("trace comparison report: ok")
    print(f"report_file: {report_path}")
    print(f"low_tier_records: {result['low_tier_records']}")
    print(f"baseline_records: {result['baseline_records']}")
    print(f"prompt_id_overlap: {result['prompt_id_overlap']}")
    print(f"schema_status: low-tier={result['low_tier_schema_status']} baseline={result['baseline_schema_status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
