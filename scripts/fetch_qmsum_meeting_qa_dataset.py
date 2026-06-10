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

from eval_datasets import truncate_words, word_count, write_jsonl


QMSUM_URLS = {
    "train": "https://raw.githubusercontent.com/Yale-LILY/QMSum/master/data/ALL/jsonl/train.jsonl",
    "val": "https://raw.githubusercontent.com/Yale-LILY/QMSum/master/data/ALL/jsonl/val.jsonl",
    "test": "https://raw.githubusercontent.com/Yale-LILY/QMSum/master/data/ALL/jsonl/test.jsonl",
}
DEFAULT_OUTPUT = Path("data/eval/qmsum_meeting_qa_100.jsonl")


def fetch_split(split: str) -> list[dict[str, Any]]:
    url = QMSUM_URLS[split]
    request = urllib.request.Request(url, headers={"User-Agent": "CC-DFlash-eval/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        text = response.read().decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def read_source_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: line {line_number} is not valid JSON ({exc})") from exc
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CC-DFlash QMSum-style meeting QA evaluation JSONL")
    parser.add_argument("--source", type=Path, default=None, help="Optional local QMSum-style source JSONL")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--splits", nargs="+", choices=sorted(QMSUM_URLS), default=["test"])
    parser.add_argument("--max-samples", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-context-words", type=int, default=500)
    parser.add_argument("--max-context-words", type=int, default=1500)
    args = parser.parse_args()

    if args.max_samples <= 0:
        raise ValueError("--max-samples must be positive")
    if args.min_context_words <= 0 or args.max_context_words < args.min_context_words:
        raise ValueError("--max-context-words must be >= --min-context-words > 0")

    if args.source is not None:
        meetings = read_source_jsonl(args.source)
        split_label = "local"
        source_label = str(args.source)
    else:
        meetings = []
        for split in args.splits:
            fetched = fetch_split(split)
            for meeting in fetched:
                meeting.setdefault("split", split)
            meetings.extend(fetched)
        split_label = "-".join(args.splits)
        source_label = "QMSum GitHub"

    rows = build_qmsum_eval_rows(
        meetings=meetings,
        max_samples=args.max_samples,
        seed=args.seed,
        min_context_words=args.min_context_words,
        max_context_words=args.max_context_words,
        split_label=split_label,
    )
    write_jsonl(rows, args.output)
    print(f"wrote {len(rows)} rows to {args.output}")
    print(f"dataset=qmsum_meeting_qa_long source={source_label} seed={args.seed}")
    print(f"context_words_min={min(row['approximate_context_words'] for row in rows)}")
    print(f"context_words_max={max(row['approximate_context_words'] for row in rows)}")
    print(f"sample_ids={[row['id'] for row in rows[:3]]}")


if __name__ == "__main__":
    main()
