"""Select controlled diagnostic records for future draft-contribution inspection."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from htfsd.metrics.diagnostic_record_selection import (
    DEFAULT_PREVIEW_MAX_CHARS,
    select_diagnostic_records_from_traces,
    write_diagnostic_record_selection_reports,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a controlled diagnostic record selection report.")
    parser.add_argument("--low-tier", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--output-dir", default="logs/reports")
    parser.add_argument("--preview-max-chars", type=int, default=DEFAULT_PREVIEW_MAX_CHARS)
    args = parser.parse_args(list(argv) if argv is not None else None)

    summary = select_diagnostic_records_from_traces(
        low_tier_path=args.low_tier,
        baseline_path=args.baseline,
        preview_max_chars=args.preview_max_chars,
    )
    markdown_path, json_path = write_diagnostic_record_selection_reports(summary=summary, output_dir=args.output_dir)
    ready = "yes" if summary.selection_ready else "no"
    print("diagnostic record selection: ok")
    print(f"markdown_report: {markdown_path}")
    print(f"json_report: {json_path}")
    print(f"selection_ready: {ready}")
    print(f"total_records: {summary.total_records}")
    print(f"eligible_valid_draft_record_count: {summary.eligible_valid_draft_record_count}")
    print(f"excluded_fallback_derived_record_count: {summary.excluded_fallback_derived_record_count}")
    print(f"excluded_unknown_contribution_record_count: {summary.excluded_unknown_contribution_record_count}")
    print(f"excluded_empty_baseline_record_count: {summary.excluded_empty_baseline_record_count}")
    print(f"excluded_prompt_mode_risk_record_count: {summary.excluded_prompt_mode_risk_record_count}")
    print(f"blocking_reasons: {summary.blocking_reasons or []}")
    return 0 if summary.selection_ready else 1


if __name__ == "__main__":
    sys.exit(main())
