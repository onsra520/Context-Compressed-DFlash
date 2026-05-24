"""Preview normalized outputs from raw-capture traces."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from htfsd.metrics.output_preview import (
    DEFAULT_PREVIEW_MAX_CHARS,
    build_output_normalization_preview,
    write_output_normalization_preview_reports,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a conservative output normalization preview report.")
    parser.add_argument("--low-tier", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--output-dir", default="logs/reports")
    parser.add_argument("--preview-max-chars", type=int, default=DEFAULT_PREVIEW_MAX_CHARS)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = build_output_normalization_preview(
        low_tier_path=args.low_tier,
        baseline_path=args.baseline,
        preview_max_chars=args.preview_max_chars,
    )
    markdown_path, json_path = write_output_normalization_preview_reports(result=result, output_dir=args.output_dir)
    ready = "yes" if result["preview_ready"] else "no"
    print("output normalization preview: ok")
    print(f"markdown_report: {markdown_path}")
    print(f"json_report: {json_path}")
    print(f"preview_ready: {ready}")
    print(f"preview_records: {len(result['preview_records'])}")
    print(f"blocking_reasons: {result['blocking_reasons']}")
    return 0 if result["preview_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
