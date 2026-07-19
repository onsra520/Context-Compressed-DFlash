#!/usr/bin/env python3
"""Adapt C3/C4 raw records for the existing target-forward diagnostic helper."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def convert(raw: list[dict[str, Any]], prompts: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {
            "phase": row["phase"],
            "prompt_id": row["sample_id"],
            "repetition": row["repetition"],
            "prompt": prompts[row["sample_id"]],
            "generated_token_ids": row["generated_token_ids"],
            "contract": {"stop_token_ids": [151645], "max_new_tokens": 256},
            "stop_reason": row["stop_reason"],
        }
        for row in raw
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--c3", type=Path, required=True)
    parser.add_argument("--c4", type=Path, required=True)
    parser.add_argument("--compression", type=Path, required=True)
    parser.add_argument("--baseline-output", type=Path, required=True)
    parser.add_argument("--dflash-output", type=Path, required=True)
    args = parser.parse_args()
    prompts = {
        row["sample_id"]: row["compressed_prompt"] for row in read_jsonl(args.compression)
    }
    write_jsonl(args.baseline_output, convert(read_jsonl(args.c3), prompts))
    write_jsonl(args.dflash_output, convert(read_jsonl(args.c4), prompts))
    print(json.dumps({"baseline": str(args.baseline_output), "dflash": str(args.dflash_output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
