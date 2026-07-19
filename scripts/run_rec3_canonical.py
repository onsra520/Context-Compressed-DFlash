#!/usr/bin/env python3
"""Thin operational entrypoint for the REC-3 canonical evidence protocol."""

from ccdf.benchmark.canonical import (
    audit,
    build_parser,
    describe,
    main,
    optional_file_identity,
    read_jsonl,
    render_report,
    run_condition,
    smoke,
    summarize,
)

__all__ = [
    "audit",
    "build_parser",
    "describe",
    "main",
    "optional_file_identity",
    "read_jsonl",
    "render_report",
    "run_condition",
    "smoke",
    "summarize",
]


if __name__ == "__main__":
    raise SystemExit(main())
