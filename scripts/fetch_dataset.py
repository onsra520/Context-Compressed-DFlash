#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from eval_datasets import (
    GSM8K_FINAL_ANSWER_INSTRUCTION,
    final_gsm8k_answer,
    read_jsonl,
    truncate_words,
    word_count,
    write_jsonl,
)

GSM8K_SPLITS = {
    "test": "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl",
    "train": "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/train.jsonl",
}

QMSUM_URLS = {
    "train": "https://raw.githubusercontent.com/Yale-LILY/QMSum/master/data/ALL/jsonl/train.jsonl",
    "val": "https://raw.githubusercontent.com/Yale-LILY/QMSum/master/data/ALL/jsonl/val.jsonl",
    "test": "https://raw.githubusercontent.com/Yale-LILY/QMSum/master/data/ALL/jsonl/test.jsonl",
}


def download_gsm8k_source(split: str, output_path: Path) -> list[dict]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    url = GSM8K_SPLITS[split]
    print(f"Downloading GSM8K {split} from {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "CC-DFlash-research/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8")
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    
    with open(output_path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    print(f"Downloaded {len(lines)} rows to {output_path}")
    return read_jsonl(output_path)


def fetch_qmsum_split(split: str) -> list[dict[str, Any]]:
    url = QMSUM_URLS[split]
    print(f"Downloading QMSum {split} from {url}...")
    request = urllib.request.Request(url, headers={"User-Agent": "CC-DFlash-eval/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        text = response.read().decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def build_gsm8k_short_rows(
    *,
    source_rows: list[dict],
    max_samples: int,
    seed: int,
    split: str,
    source_path: Path,
) -> list[dict]:
    if not source_rows:
        raise ValueError("no GSM8K rows provided")
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


def format_transcript(meeting_transcripts: list[dict[str, Any]]) -> str:
    parts = []
    for turn in meeting_transcripts:
        speaker = str(turn.get("speaker") or "Speaker").strip()
        content = str(turn.get("content") or "").strip()
        if content:
            parts.append(f"{speaker}: {content}")
    return "\n".join(parts)


def _qa_pairs(meeting: dict[str, Any]) -> list[dict[str, str]]:
    if "QA_pairs" in meeting:
        return [
            {"question": str(item.get("question", "")).strip(), "answer": str(item.get("answer", "")).strip()}
            for item in meeting.get("QA_pairs", [])
        ]
    raw = meeting.get("specific_query_list") or meeting.get("general_query_list") or []
    return [
        {"question": str(item.get("query", "")).strip(), "answer": str(item.get("answer", "")).strip()}
        for item in raw
    ]


def _transcript(meeting: dict[str, Any]) -> str:
    if isinstance(meeting.get("transcript"), str):
        return meeting["transcript"].strip()
    return format_transcript(meeting.get("meeting_transcripts", []))


def build_qmsum_eval_rows(
    *,
    meetings: list[dict[str, Any]],
    max_samples: int,
    seed: int,
    min_context_words: int,
    max_context_words: int,
    split_label: str,
    source_label: str,
) -> list[dict[str, Any]]:
    candidates = []
    for meeting_index, meeting in enumerate(meetings):
        transcript = _transcript(meeting)
        if word_count(transcript) < min_context_words:
            continue
        context = truncate_words(transcript, max_context_words)
        for qa_index, qa in enumerate(_qa_pairs(meeting)):
            question = qa["question"]
            answer = qa["answer"]
            if not question or not answer:
                continue
            candidates.append((meeting_index, qa_index, context, question, answer, meeting))
    if not candidates:
        raise ValueError("no QMSum meeting QA rows survived filtering")
    rng = random.Random(seed)
    selected = rng.sample(candidates, min(max_samples, len(candidates)))
    rows = []
    for index, (meeting_index, qa_index, context, question, answer, meeting) in enumerate(selected, start=1):
        prompt = (
            "Meeting transcript:\n"
            f"{context}\n\n"
            f"Question: {question}\n\n"
            "Answer using only the meeting transcript. A concise answer is enough."
        )
        rows.append(
            {
                "id": f"qmsum_meeting_qa_{split_label}_{index:04d}",
                "dataset_name": "qmsum_meeting_qa_long",
                "source": "qmsum",
                "source_mode": "download_or_local_jsonl",
                "domain": "meeting_qa_long_context",
                "context": context,
                "question": question,
                "answer": answer,
                "ground_truth_answer": answer,
                "expected_answer": answer,
                "prompt": prompt,
                "evidence": "Expected answer is the QMSum meeting QA reference answer or summary.",
                "quality_policy": "normalized_text_containment_proxy",
                "approximate_context_words": word_count(context),
                "approximate_prompt_words": word_count(prompt),
                "original_dataset_reference": {
                    "dataset": "QMSum",
                    "split": str(meeting.get("split") or split_label),
                    "meeting_index": meeting.get("idx", meeting_index),
                    "qa_index": qa_index,
                },
                "evaluation_role": "long_context_speed_prefill_compression_overhead",
            }
        )
    return rows


def handle_gsm8k(args):
    source_path = Path("data/raw/gsm8k_source.jsonl")
    if not source_path.exists():
        source_rows = download_gsm8k_source("test", source_path)
    else:
        source_rows = read_jsonl(source_path)

    rows = build_gsm8k_short_rows(
        source_rows=source_rows,
        max_samples=args.max_samples,
        seed=args.seed,
        split="test",
        source_path=source_path,
    )
    
    output = Path(args.output) if args.output else Path("data/eval/gsm8k_100.jsonl")
    write_jsonl(rows, output)
    print(f"wrote {len(rows)} rows to {output}")


def handle_qmsum(args):
    meetings = []
    splits = ["test"]
    for split in splits:
        fetched = fetch_qmsum_split(split)
        for meeting in fetched:
            meeting.setdefault("split", split)
        meetings.extend(fetched)
    split_label = "-".join(splits)
    source_label = "QMSum GitHub"

    rows = build_qmsum_eval_rows(
        meetings=meetings,
        max_samples=args.max_samples,
        seed=args.seed,
        min_context_words=500,
        max_context_words=1500,
        split_label=split_label,
        source_label=source_label,
    )
    
    output = Path(args.output) if args.output else Path("data/eval/qmsum_meeting_qa_100.jsonl")
    write_jsonl(rows, output)
    print(f"wrote {len(rows)} rows to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and format CC-DFlash evaluation datasets")
    subparsers = parser.add_subparsers(dest="dataset", required=True)

    gsm8k_parser = subparsers.add_parser("gsm8k", help="Fetch GSM8K short-context dataset")
    gsm8k_parser.add_argument("--output", type=str, default="data/eval/gsm8k_100.jsonl")
    gsm8k_parser.add_argument("--max-samples", type=int, default=100)
    gsm8k_parser.add_argument("--seed", type=int, default=42)

    qmsum_parser = subparsers.add_parser("qmsum_meeting_qa", help="Fetch QMSum long-context dataset")
    qmsum_parser.add_argument("--output", type=str, default="data/eval/qmsum_meeting_qa_100.jsonl")
    qmsum_parser.add_argument("--max-samples", type=int, default=100)
    qmsum_parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    if args.dataset == "gsm8k":
        handle_gsm8k(args)
    elif args.dataset == "qmsum_meeting_qa":
        handle_qmsum(args)


if __name__ == "__main__":
    main()
