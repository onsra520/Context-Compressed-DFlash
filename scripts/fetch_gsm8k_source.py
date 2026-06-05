"""
fetch_gsm8k_source.py
=====================
Download GSM8K test split từ official OpenAI GitHub repo.

Nguồn: https://github.com/openai/grade-school-math
  - 1,319 bài toán tiểu học (test split)
  - Format: {"question": "...", "answer": "...\n#### N"}
  - License: MIT

Output: data/raw/gsm8k_source.jsonl (format gốc của OpenAI, không thay đổi)

Usage:
  python scripts/fetch_gsm8k_source.py
  python scripts/fetch_gsm8k_source.py --output data/raw/gsm8k_source.jsonl --split test
  python scripts/fetch_gsm8k_source.py --split train  # 7473 bài train
"""

import argparse
import json
import pathlib
import sys
import urllib.request

SPLITS = {
    "test": (
        "https://raw.githubusercontent.com/openai/grade-school-math"
        "/master/grade_school_math/data/test.jsonl"
    ),
    "train": (
        "https://raw.githubusercontent.com/openai/grade-school-math"
        "/master/grade_school_math/data/train.jsonl"
    ),
}


def main():
    parser = argparse.ArgumentParser(description="Download GSM8K source JSONL for CC-DFlash")
    parser.add_argument(
        "--output",
        default="data/raw/gsm8k_source.jsonl",
        help="Output path (default: data/raw/gsm8k_source.jsonl)",
    )
    parser.add_argument(
        "--split",
        choices=["test", "train"],
        default="test",
        help="Which split to download (default: test — 1319 rows)",
    )
    args = parser.parse_args()

    url = SPLITS[args.split]
    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("CC-DFlash: Downloading GSM8K source JSONL")
    print(f"  Split  : {args.split}")
    print(f"  Source : {url}")
    print(f"  Output : {output_path}")
    print()

    print("Downloading...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "CC-DFlash-research/1.0 (academic)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8")

    lines = [l.strip() for l in raw.splitlines() if l.strip()]

    # Validate JSON and check #### answer format
    valid = 0
    invalid = 0
    missing_answer_marker = 0
    for i, line in enumerate(lines):
        try:
            row = json.loads(line)
            if "question" not in row or "answer" not in row:
                invalid += 1
                continue
            if "####" not in row["answer"]:
                missing_answer_marker += 1
            valid += 1
        except json.JSONDecodeError:
            invalid += 1

    print(f"  Rows downloaded       : {len(lines)}")
    print(f"  Valid JSON rows        : {valid}")
    print(f"  Invalid rows           : {invalid}")
    print(f"  Missing #### marker    : {missing_answer_marker} (OK — those use different format)")

    if invalid > 0:
        print(f"  WARNING: {invalid} invalid rows found", file=sys.stderr)

    # Write as-is (preserve original OpenAI format)
    with open(output_path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

    size_kb = output_path.stat().st_size / 1024
    print(f"  File size              : {size_kb:.1f} KB")
    print()
    print(f"✓ Done: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
