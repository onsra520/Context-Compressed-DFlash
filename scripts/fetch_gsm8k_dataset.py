#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from eval_datasets import (
    GSM8K_FINAL_ANSWER_INSTRUCTION,
    final_gsm8k_answer,
    read_jsonl,
    word_count,
    write_jsonl,
)


DEFAULT_SOURCE = Path("data/raw/gsm8k_source.jsonl")
DEFAULT_OUTPUT = Path("data/eval/gsm8k_100.jsonl")


def build_gsm8k_short_rows(
    *,
    source_path: Path,
    max_samples: int,
    seed: int,
    split: str,
) -> list[dict]:
    source_rows = read_jsonl(source_path)
    if not source_rows:
        raise ValueError(f"no GSM8K rows found in {source_path}")
    if max_samples <= 0:
        raise ValueError("max_samples must be positive")
    rng = random.Random(seed)
    selected = rng.sample(source_rows, min(max_samples, len(source_rows)))
    rows = []
    for index, row in enumerate(selected, start=1):
        question = str(row["question"]).strip()
        answer = str(row["answer"]).strip()
        expected_answer = final_gsm8k_answer(answer)
        context = "Short-context numeric QA. Solve the math word problem and preserve the original question."
        prompt = (
            f"{context}\n\n"
            f"Question: {question}\n\n"
            f"{GSM8K_FINAL_ANSWER_INSTRUCTION}"
        )
        rows.append(
            {
                "id": f"gsm8k_short_{split}_{index:04d}",
                "dataset_name": "gsm8k_short",
                "source": "gsm8k",
                "source_mode": "local_jsonl",
                "domain": "numeric_qa",
                "context": context,
                "question": question,
                "answer": expected_answer,
                "ground_truth_answer": expected_answer,
                "expected_answer": expected_answer,
                "prompt": prompt,
                "evidence": "The expected answer is the GSM8K final numeric answer after the #### marker.",
                "quality_policy": "numeric_extraction_exact_match_proxy",
                "approximate_context_words": word_count(context),
                "approximate_prompt_words": word_count(prompt),
                "original_dataset_reference": {
                    "dataset": "GSM8K",
                    "split": split,
                    "source_path": str(source_path),
                },
                "evaluation_role": "short_context_numeric_quality",
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CC-DFlash GSM8K short-context evaluation JSONL")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-samples", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--split", default="test")
    args = parser.parse_args()

    rows = build_gsm8k_short_rows(
        source_path=args.source,
        max_samples=args.max_samples,
        seed=args.seed,
        split=args.split,
    )
    write_jsonl(rows, args.output)
    print(f"wrote {len(rows)} rows to {args.output}")
    print(f"dataset=gsm8k_short source={args.source} seed={args.seed} split={args.split}")
    print(f"sample_ids={[row['id'] for row in rows[:3]]}")
    print(f"sample_expected_answers={[row['expected_answer'] for row in rows[:3]]}")


if __name__ == "__main__":
    main()
