from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_OUTPUT = Path("data/eval/gsm8k_100.jsonl")


SAMPLE_GSM8K_ROWS = [
    {
        "question": (
            "Mara has 14 red beads and buys 9 more red beads. She gives 6 red beads to her sister. "
            "How many red beads does Mara have left?"
        ),
        "answer": "Mara has 14 + 9 = 23 red beads after buying more. She gives away 6, so 23 - 6 = 17. #### 17",
    },
    {
        "question": (
            "A bakery made 8 trays of muffins with 6 muffins on each tray. By noon, 22 muffins were sold. "
            "How many muffins were left?"
        ),
        "answer": "The bakery made 8 * 6 = 48 muffins. After selling 22, it had 48 - 22 = 26 left. #### 26",
    },
    {
        "question": (
            "Noah reads 12 pages on Monday, 15 pages on Tuesday, and 18 pages on Wednesday. "
            "How many pages does he read in total?"
        ),
        "answer": "Noah reads 12 + 15 + 18 = 45 pages. #### 45",
    },
]


@dataclass(frozen=True)
class BuildOptions:
    output: Path = DEFAULT_OUTPUT
    max_samples: int = 5
    seed: int = 41
    split: str = "test"
    source_mode: str = "sample"
    gsm8k_jsonl: Path | None = None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _final_answer(answer: str) -> str:
    if "####" in answer:
        return answer.rsplit("####", 1)[1].strip()
    return answer.strip().splitlines()[-1].strip()


def load_gsm8k_rows(options: BuildOptions) -> list[dict[str, Any]]:
    if options.gsm8k_jsonl is not None:
        return _read_jsonl(options.gsm8k_jsonl)
    if options.source_mode == "sample":
        return list(SAMPLE_GSM8K_ROWS)
    if options.source_mode == "hf":
        from datasets import load_dataset

        return list(load_dataset("openai/gsm8k", "main", split=options.split))
    raise ValueError(f"Unsupported source mode: {options.source_mode}")


def build_rows(options: BuildOptions) -> list[dict[str, Any]]:
    rng = random.Random(options.seed)
    gsm8k_rows = load_gsm8k_rows(options)
    if not gsm8k_rows:
        raise ValueError("No GSM8K rows available")

    selected_gsm8k = list(enumerate(gsm8k_rows))
    rng.shuffle(selected_gsm8k)

    rows = []
    for source_index, source_row in selected_gsm8k:
        if len(rows) >= options.max_samples:
            break

        question = str(source_row["question"]).strip()
        answer_text = str(source_row["answer"]).strip()
        ground_truth = _final_answer(answer_text)

        context = "Short-context numeric QA. Solve the math word problem and preserve the original question."
        prompt = (
            f"{context}\n\n"
            f"Question: {question}\n\n"
            "Answer the question clearly. Format the final numeric answer after #### at the end."
        )

        row_id = f"gsm8k_short_{options.split}_{len(rows) + 1:04d}"

        rows.append(
            {
                "id": row_id,
                "dataset_name": "gsm8k_short",
                "source": "gsm8k",
                "source_mode": options.source_mode,
                "domain": "numeric_qa",
                "question": question,
                "answer": ground_truth,
                "ground_truth_answer": ground_truth,
                "expected_answer": ground_truth,
                "context": context,
                "prompt": prompt,
                "evidence": "The answer is derived from the GSM8K question.",
                "quality_policy": "numeric_extraction_exact_match_proxy",
                "approximate_context_words": len(context.split()),
                "approximate_context_tokens": round(len(context.split()) * 1.3),
                "approximate_prompt_words": len(prompt.split()),
                "token_length_metadata": {
                    "token_count_method": "word_estimate",
                    "approximate_context_words": len(context.split()),
                    "approximate_context_tokens": round(len(context.split()) * 1.3),
                },
                "original_dataset_reference": {
                    "dataset": "openai/gsm8k",
                    "config": "main",
                    "split": options.split,
                    "index": source_index,
                    "source_mode": options.source_mode,
                    "gsm8k_source": str(options.gsm8k_jsonl) if options.gsm8k_jsonl is not None else "datasets:openai/gsm8k",
                },
                "augmentation_metadata": {
                    "seed": options.seed,
                    "question_preserved": question in prompt,
                },
            }
        )

    return rows


def validate_rows(rows: Iterable[dict[str, Any]]) -> None:
    required = {
        "id",
        "source",
        "question",
        "answer",
        "ground_truth_answer",
        "expected_answer",
        "context",
        "prompt",
        "original_dataset_reference",
        "augmentation_metadata",
        "approximate_context_words",
    }
    for row in rows:
        missing = required - set(row)
        if missing:
            raise ValueError(f"{row.get('id', '<unknown>')}: missing fields {sorted(missing)}")


def write_jsonl(rows: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def parse_args() -> BuildOptions:
    parser = argparse.ArgumentParser(description="Create GSM8K short-context JSONL dataset")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-samples", type=int, default=5)
    parser.add_argument("--seed", type=int, default=41)
    parser.add_argument("--split", default="test")
    parser.add_argument("--source-mode", choices=["sample", "hf"], default="sample")
    parser.add_argument("--gsm8k-jsonl", type=Path, default=None)
    args = parser.parse_args()

    if args.max_samples <= 0:
        raise ValueError("--max-samples must be positive")

    return BuildOptions(
        output=args.output,
        max_samples=args.max_samples,
        seed=args.seed,
        split=args.split,
        source_mode=args.source_mode,
        gsm8k_jsonl=args.gsm8k_jsonl,
    )


def main() -> None:
    options = parse_args()
    rows = build_rows(options)
    validate_rows(rows)
    write_jsonl(rows, options.output)
    print(f"wrote {len(rows)} rows to {options.output}")
    print(f"source_mode={options.source_mode} split={options.split} seed={options.seed}")


if __name__ == "__main__":
    main()
