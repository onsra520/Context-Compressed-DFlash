"""Inspect compact trace JSON files for required schema fields."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from htfsd.metrics.trace_schema import TraceMode, validate_trace_file


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a low-tier trace JSON schema.")
    parser.add_argument("trace_file")
    parser.add_argument("--mode", choices=("live", "controlled-fallback"), required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = validate_trace_file(args.trace_file, mode=args.mode)
    print(f"records: {result.record_count}")
    print(f"mode: {result.mode}")
    if result.ok:
        print("trace schema: ok")
        return 0

    print("trace schema: failed")
    missing = sorted({field for error in result.record_errors for field in error.missing_fields})
    if missing:
        print("missing_fields:")
        for field in missing:
            print(f"  - {field}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
