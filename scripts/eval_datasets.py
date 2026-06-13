from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DATASET_REGISTRY = {
    "gsm8k_short": {
        "path": Path("data/eval/gsm8k_100.jsonl"),
        "quality_policy": "numeric_extraction_exact_match_proxy",
        "description": "GSM8K short-context numeric QA evaluation dataset",
    },
    "qmsum_meeting_qa_long": {
        "path": Path("data/eval/qmsum_meeting_qa_100.jsonl"),
        "quality_policy": "normalized_text_containment_proxy",
        "description": "QMSum-style meeting QA long-context evaluation dataset",
    },
}

GSM8K_FINAL_ANSWER_INSTRUCTION = (
    "End with exactly one line:\n"
    "Final answer: <number>"
)

QMSUM_BALANCED_ANSWER_INSTRUCTION = (
    "Answer in 3-6 concise sentences.\n"
    "Include the key entities, decisions, reasons, and supporting details needed to answer the question.\n"
    "Do not repeat the full context.\n"
    "Do not include unrelated meeting details.\n"
    "Use only information supported by the meeting context."
)


@dataclass(frozen=True)
class EvalDatasetRow:
    id: str
    dataset_name: str
    context: str
    question: str
    expected_answer: str
    prompt: str
    domain: str
    evidence: str
    approximate_context_words: int
    quality_policy: str
    raw: dict[str, Any]


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def truncate_words(text: str, max_words: int | None) -> str:
    if max_words is None or max_words <= 0:
        return text
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: line {line_number} is not valid JSON ({exc})") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}: line {line_number} is not a JSON object")
        rows.append(row)
    return rows


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def final_gsm8k_answer(answer: str) -> str:
    if "####" in answer:
        return answer.rsplit("####", 1)[1].strip()
    return answer.strip().splitlines()[-1].strip()


def normalize_eval_row(row: dict[str, Any], dataset_name: str) -> EvalDatasetRow:
    for field_name in ("id", "context", "question", "expected_answer"):
        value = row.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{dataset_name}: row missing non-empty `{field_name}`")
    prompt = row.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        prompt = f"{row['context']}\n\nQuestion: {row['question']}"
    if dataset_name == "gsm8k_short" and "Final answer: <number>" not in prompt:
        prompt = f"{prompt.rstrip()}\n\n{GSM8K_FINAL_ANSWER_INSTRUCTION}"
    if dataset_name == "qmsum_meeting_qa_long" and QMSUM_BALANCED_ANSWER_INSTRUCTION not in prompt:
        prompt = f"{prompt.rstrip()}\n\n{QMSUM_BALANCED_ANSWER_INSTRUCTION}"
    domain = str(row.get("domain", dataset_name))
    evidence = str(row.get("evidence", ""))
    approximate_context_words = row.get("approximate_context_words")
    if not isinstance(approximate_context_words, int) or isinstance(approximate_context_words, bool):
        approximate_context_words = word_count(str(row["context"]))
    quality_policy = str(row.get("quality_policy") or DATASET_REGISTRY[dataset_name]["quality_policy"])
    return EvalDatasetRow(
        id=str(row["id"]),
        dataset_name=dataset_name,
        context=str(row["context"]),
        question=str(row["question"]),
        expected_answer=str(row["expected_answer"]),
        prompt=str(prompt),
        domain=domain,
        evidence=evidence,
        approximate_context_words=approximate_context_words,
        quality_policy=quality_policy,
        raw=row,
    )


def load_eval_dataset(dataset_name: str, path: Path | None = None) -> list[EvalDatasetRow]:
    if dataset_name not in DATASET_REGISTRY:
        raise ValueError(f"Unsupported dataset: {dataset_name}")
    dataset_path = path or DATASET_REGISTRY[dataset_name]["path"]
    rows = read_jsonl(dataset_path)
    if not rows:
        raise ValueError(f"dataset contains no rows: {dataset_path}")
    return [normalize_eval_row(row, dataset_name) for row in rows]


def select_eval_dataset_rows(
    dataset_name: str,
    *,
    n: int,
    seed: int,
    path: Path | None = None,
) -> list[EvalDatasetRow]:
    if n <= 0:
        raise ValueError("n must be positive")
    rows = load_eval_dataset(dataset_name, path)
    rng = random.Random(seed)
    if n <= len(rows):
        return rng.sample(rows, n)
    selected = list(rows)
    while len(selected) < n:
        selected.extend(rng.sample(rows, min(len(rows), n - len(selected))))
    return selected[:n]
