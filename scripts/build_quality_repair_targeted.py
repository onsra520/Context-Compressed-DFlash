#!/usr/bin/env python3
"""Build the two locked GSM8K quality-repair regression samples."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ccdf.compression.fact_validation import validate_facts
from ccdf.datasets.pipeline import build_samples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=Path("data/raw/gsm8k/gsm8k_test.jsonl"))
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    args = parser.parse_args()
    raw = [json.loads(line) for line in args.raw.read_text(encoding="utf-8").splitlines()]
    selection = {
        "seed": 42,
        "gsm8k": [
            {"upstream_row_index": 158},  # Raphael: sentence-final $20.
            {"upstream_row_index": 104},  # Poppy: quarter/third/remaining.
        ],
    }
    samples = build_samples(raw, selection, "gsm8k")
    args.samples.parent.mkdir(parents=True, exist_ok=True)
    args.samples.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in samples),
        encoding="utf-8",
    )
    currency_original = samples[0]["prompt"]
    fraction_original = samples[1]["prompt"]
    old_broken = {
        samples[0]["sample_id"]: validate_facts(
            currency_original, currency_original.replace("$20.", ".", 1)
        ).to_dict(),
        samples[1]["sample_id"]: validate_facts(
            fraction_original,
            fraction_original.replace("a quarter of the pieces", "pieces", 1).replace(
                "a third of the remaining pieces", "pieces", 1
            ),
        ).to_dict(),
    }
    payload = {
        "schema": "ccdf.quality-repair-targeted-validation.v1",
        "sample_ids": [row["sample_id"] for row in samples],
        "old_broken_candidates_detected": all(not value["passed"] for value in old_broken.values()),
        "old_broken_validation": old_broken,
    }
    args.validation.parent.mkdir(parents=True, exist_ok=True)
    args.validation.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["old_broken_candidates_detected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
