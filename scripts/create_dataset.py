from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_OUTPUT = Path("data/processed/gsm8k_wikipedia_augmented_smoke.jsonl")


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
    {
        "question": (
            "A teacher packs 5 boxes with 9 pencils in each box. She then adds 7 loose pencils. "
            "How many pencils does she have altogether?"
        ),
        "answer": "The boxes contain 5 * 9 = 45 pencils. With 7 loose pencils, she has 45 + 7 = 52. #### 52",
    },
    {
        "question": (
            "Lina saves 11 dollars each week for 4 weeks, then spends 13 dollars on a book. "
            "How many dollars does she have left?"
        ),
        "answer": "Lina saves 11 * 4 = 44 dollars. She spends 13, leaving 44 - 13 = 31. #### 31",
    },
]


SAMPLE_WIKIPEDIA_ROWS = [
    {
        "title": "Library",
        "url": "https://en.wikipedia.org/wiki/Library",
        "text": (
            "A library is a collection of materials, books, or media that are accessible for use and not just "
            "for display purposes. Libraries often provide quiet reading spaces, reference help, community "
            "programming, catalog systems, and access to digital resources. A public library may serve many "
            "neighborhoods and can support education, research, and local cultural activity."
        ),
    },
    {
        "title": "Botanical garden",
        "url": "https://en.wikipedia.org/wiki/Botanical_garden",
        "text": (
            "A botanical garden is a curated place where plants are grown, labeled, studied, and displayed. "
            "Such gardens may include greenhouses, seed collections, walking paths, conservation programs, "
            "and educational exhibits. Visitors often learn about plant habitats, pollination, climate, and "
            "the relationship between living collections and scientific research."
        ),
    },
    {
        "title": "Bridge",
        "url": "https://en.wikipedia.org/wiki/Bridge",
        "text": (
            "A bridge is a structure built to span a physical obstacle such as water, a valley, or a road. "
            "Bridge design considers materials, load, weather, maintenance, and the movement of people or "
            "vehicles. Common forms include beam, arch, suspension, and truss bridges, each with distinct "
            "engineering tradeoffs and historical examples."
        ),
    },
    {
        "title": "Museum",
        "url": "https://en.wikipedia.org/wiki/Museum",
        "text": (
            "A museum is an institution that cares for collections of artifacts and other objects of artistic, "
            "cultural, historical, or scientific importance. Museums may host exhibitions, preserve records, "
            "support research, and provide learning programs. Many museums organize collections around themes, "
            "regions, time periods, or particular fields of study."
        ),
    },
    {
        "title": "Weather forecasting",
        "url": "https://en.wikipedia.org/wiki/Weather_forecasting",
        "text": (
            "Weather forecasting applies science and technology to predict atmospheric conditions for a given "
            "place and time. Forecasters use observations, satellite data, radar, numerical models, and local "
            "knowledge. Forecasts can support travel planning, agriculture, emergency preparation, and daily "
            "decisions about outdoor activities."
        ),
    },
]


@dataclass(frozen=True)
class BuildOptions:
    output: Path = DEFAULT_OUTPUT
    max_samples: int = 5
    min_context_words: int = 220
    max_context_words: int = 360
    seed: int = 41
    split: str = "test"
    source_mode: str = "sample"
    gsm8k_jsonl: Path | None = None
    wikipedia_jsonl: Path | None = None
    tokenizer: str | None = None
    max_leakage_resample_attempts: int = 100


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


def _normalize_for_leakage(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def _normalized_numbers(text: str) -> set[str]:
    numbers = set()
    for match in re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", text):
        normalized = match.replace(",", "")
        if normalized:
            numbers.add(normalized)
    return numbers


def _contains_answer(text: str, answer: str) -> bool:
    normalized_answer = _normalize_for_leakage(answer)
    if not normalized_answer:
        return False
    normalized_text = _normalize_for_leakage(text)
    if not normalized_text:
        return False
    answer_numbers = _normalized_numbers(answer)
    if answer_numbers and answer_numbers.intersection(_normalized_numbers(text)):
        return True
    return re.search(rf"(?<![a-z0-9]){re.escape(normalized_answer)}(?![a-z0-9])", normalized_text) is not None


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def load_gsm8k_rows(options: BuildOptions) -> list[dict[str, Any]]:
    if options.gsm8k_jsonl is not None:
        return _read_jsonl(options.gsm8k_jsonl)
    if options.source_mode == "sample":
        return list(SAMPLE_GSM8K_ROWS)
    if options.source_mode == "hf":
        from datasets import load_dataset

        return list(load_dataset("openai/gsm8k", "main", split=options.split))
    raise ValueError(f"Unsupported source mode: {options.source_mode}")


def load_wikipedia_rows(options: BuildOptions) -> list[dict[str, Any]]:
    if options.wikipedia_jsonl is not None:
        return _read_jsonl(options.wikipedia_jsonl)
    return list(SAMPLE_WIKIPEDIA_ROWS)


def _select_distractors_once(
    wikipedia_rows: list[dict[str, Any]],
    *,
    answer: str,
    rng: random.Random,
    min_words: int,
    max_words: int,
) -> tuple[str, list[dict[str, str]], bool]:
    candidates = list(wikipedia_rows)
    rng.shuffle(candidates)
    selected: list[dict[str, str]] = []
    paragraphs: list[str] = []

    for row in candidates:
        title = str(row.get("title", "untitled")).strip() or "untitled"
        text = str(row.get("text", "")).strip()
        if not text or _contains_answer(text, answer):
            continue
        selected.append({"title": title, "url": str(row.get("url", ""))})
        paragraphs.append(f"[Wikipedia: {title}] {text}")
        if _word_count(" ".join(paragraphs)) >= min_words:
            break

    if not paragraphs:
        raise ValueError(f"No Wikipedia distractor survived leakage guard for answer: {answer!r}")

    while _word_count(" ".join(paragraphs)) < min_words:
        paragraphs.append(paragraphs[len(paragraphs) % len(selected)])

    context = "\n\n".join(paragraphs)
    context = _truncate_words(context, max_words)
    return context, selected, _contains_answer(context, answer)


def _build_context_and_prompt(
    *,
    wikipedia_rows: list[dict[str, Any]],
    question: str,
    answer: str,
    rng: random.Random,
    min_words: int,
    max_words: int,
    max_attempts: int,
) -> tuple[str, str, list[dict[str, str]], dict[str, Any]]:
    last_reason = "no attempt made"
    saw_answer_in_distractor = False
    context_prefix = (
        "The following background passages are Wikipedia-derived distractors. "
        "They may be irrelevant to the math question and should not be treated as containing the answer.\n\n"
    )
    prefix_words = _word_count(context_prefix)
    body_min_words = max(1, min_words - prefix_words)
    body_max_words = max(body_min_words, max_words - prefix_words)

    for attempt in range(1, max_attempts + 1):
        try:
            context_body, distractors, answer_in_distractor = _select_distractors_once(
                wikipedia_rows,
                answer=answer,
                rng=rng,
                min_words=body_min_words,
                max_words=body_max_words,
            )
        except ValueError as exc:
            last_reason = str(exc)
            saw_answer_in_distractor = True
            continue

        saw_answer_in_distractor = saw_answer_in_distractor or answer_in_distractor
        context = f"{context_prefix}{context_body}"
        prompt = f"{context}\n\nQuestion: {question}"
        answer_in_context = _contains_answer(context, answer)
        answer_in_prompt = _contains_answer(prompt, answer)
        if not answer_in_distractor and not answer_in_context and not answer_in_prompt:
            return (
                context,
                prompt,
                distractors,
                {
                    "leakage_resample_attempts": attempt,
                    "answer_in_distractor": answer_in_distractor,
                    "answer_in_context": answer_in_context,
                    "answer_in_prompt": answer_in_prompt,
                    "saw_answer_in_rejected_distractor": saw_answer_in_distractor,
                },
            )

        leaked_fields = [
            field_name
            for field_name, leaked in [
                ("distractor", answer_in_distractor),
                ("context", answer_in_context),
                ("prompt", answer_in_prompt),
            ]
            if leaked
        ]
        last_reason = f"answer leaked into {', '.join(leaked_fields)}"

    raise ValueError(f"could not build leakage-safe prompt after {max_attempts} attempts: {last_reason}")


def _token_metadata(text: str, tokenizer_name: str | None) -> dict[str, Any]:
    words = _word_count(text)
    if tokenizer_name is None:
        return {
            "token_count_method": "word_estimate",
            "approximate_context_words": words,
            "approximate_context_tokens": round(words * 1.3),
        }

    try:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(tokenizer_name, trust_remote_code=True)
        return {
            "token_count_method": f"tokenizer:{tokenizer_name}",
            "approximate_context_words": words,
            "approximate_context_tokens": len(tokenizer.encode(text, add_special_tokens=False)),
        }
    except Exception as exc:
        return {
            "token_count_method": f"word_estimate_tokenizer_unavailable:{type(exc).__name__}",
            "approximate_context_words": words,
            "approximate_context_tokens": round(words * 1.3),
        }


def build_rows(options: BuildOptions) -> list[dict[str, Any]]:
    if options.max_leakage_resample_attempts <= 0:
        raise ValueError("max_leakage_resample_attempts must be positive")

    rng = random.Random(options.seed)
    gsm8k_rows = load_gsm8k_rows(options)
    wikipedia_rows = load_wikipedia_rows(options)
    if not gsm8k_rows:
        raise ValueError("No GSM8K rows available")
    if not wikipedia_rows:
        raise ValueError("No Wikipedia rows available")

    selected_gsm8k = list(enumerate(gsm8k_rows))
    rng.shuffle(selected_gsm8k)

    rows = []
    skipped_due_to_leakage = 0
    for source_index, source_row in selected_gsm8k:
        if len(rows) >= options.max_samples:
            break

        question = str(source_row["question"]).strip()
        answer_text = str(source_row["answer"]).strip()
        ground_truth = _final_answer(answer_text)
        try:
            context, prompt, distractors, leakage_metadata = _build_context_and_prompt(
                wikipedia_rows=wikipedia_rows,
                question=question,
                answer=ground_truth,
                rng=rng,
                min_words=options.min_context_words,
                max_words=options.max_context_words,
                max_attempts=options.max_leakage_resample_attempts,
            )
        except ValueError:
            skipped_due_to_leakage += 1
            continue

        token_metadata = _token_metadata(context, options.tokenizer)
        row_id = f"gsm8k_wiki_{options.split}_{len(rows) + 1:04d}"
        answer_in_context = _contains_answer(context, ground_truth)
        answer_in_prompt = _contains_answer(prompt, ground_truth)

        rows.append(
            {
                "id": row_id,
                "source": "gsm8k+wikipedia",
                "source_mode": options.source_mode,
                "domain": "math_augmented_wikipedia",
                "question": question,
                "answer": ground_truth,
                "ground_truth_answer": ground_truth,
                "expected_answer": ground_truth,
                "context": context,
                "prompt": prompt,
                "evidence": "The answer is derived from the GSM8K question; Wikipedia passages are distractors.",
                "noise_type": "wikipedia_distractor",
                "approximate_context_words": token_metadata["approximate_context_words"],
                "approximate_context_tokens": token_metadata["approximate_context_tokens"],
                "leakage_resample_attempts": leakage_metadata["leakage_resample_attempts"],
                "skipped_due_to_leakage": False,
                "token_length_metadata": token_metadata,
                "original_dataset_reference": {
                    "dataset": "openai/gsm8k",
                    "config": "main",
                    "split": options.split,
                    "index": source_index,
                    "source_mode": options.source_mode,
                    "gsm8k_source": str(options.gsm8k_jsonl) if options.gsm8k_jsonl is not None else "datasets:openai/gsm8k",
                },
                "augmentation_metadata": {
                    "wikipedia_source": "sample" if options.wikipedia_jsonl is None else str(options.wikipedia_jsonl),
                    "distractor_titles": [item["title"] for item in distractors],
                    "distractor_urls": [item["url"] for item in distractors],
                    "seed": options.seed,
                    "target_context_words": [options.min_context_words, options.max_context_words],
                    "answer_leakage_guard": "normalized answer and numeric variants excluded from distractor context and prompt",
                    "leakage_resample_attempts": leakage_metadata["leakage_resample_attempts"],
                    "max_leakage_resample_attempts": options.max_leakage_resample_attempts,
                    "skipped_source_rows_due_to_leakage_before_this_row": skipped_due_to_leakage,
                    "saw_answer_in_rejected_distractor": leakage_metadata["saw_answer_in_rejected_distractor"],
                    "answer_in_distractor": leakage_metadata["answer_in_distractor"],
                    "answer_in_context": answer_in_context,
                    "answer_in_prompt": answer_in_prompt,
                    "question_preserved": question in prompt,
                },
            }
        )

    if len(rows) < options.max_samples:
        raise ValueError(
            "Could not generate requested leakage-safe dataset: "
            f"requested sample count: {options.max_samples}; "
            f"generated clean row count: {len(rows)}; "
            f"skipped GSM8K row count: {skipped_due_to_leakage}; "
            f"leakage retry limit: {options.max_leakage_resample_attempts}"
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
        if row["question"] not in row["prompt"]:
            raise ValueError(f"{row['id']}: question was not preserved in prompt")
        if row["augmentation_metadata"].get("answer_in_distractor"):
            raise ValueError(f"{row['id']}: answer leaked into Wikipedia distractor context")
        if row["augmentation_metadata"].get("answer_in_context"):
            raise ValueError(f"{row['id']}: answer leaked into model-visible context")
        if row["augmentation_metadata"].get("answer_in_prompt"):
            raise ValueError(f"{row['id']}: answer leaked into model-visible prompt")


def write_jsonl(rows: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def parse_args() -> BuildOptions:
    parser = argparse.ArgumentParser(description="Create GSM8K + Wikipedia augmented long-context JSONL dataset")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-samples", type=int, default=5)
    parser.add_argument("--min-context-words", type=int, default=220)
    parser.add_argument("--max-context-words", type=int, default=360)
    parser.add_argument("--seed", type=int, default=41)
    parser.add_argument("--split", default="test")
    parser.add_argument("--source-mode", choices=["sample", "hf"], default="sample")
    parser.add_argument("--gsm8k-jsonl", type=Path, default=None)
    parser.add_argument("--wikipedia-jsonl", type=Path, default=None)
    parser.add_argument("--tokenizer", default=None)
    parser.add_argument("--max-leakage-resample-attempts", type=int, default=100)
    args = parser.parse_args()

    if args.max_samples <= 0:
        raise ValueError("--max-samples must be positive")
    if args.min_context_words <= 0 or args.max_context_words < args.min_context_words:
        raise ValueError("--max-context-words must be >= --min-context-words > 0")
    if args.max_leakage_resample_attempts <= 0:
        raise ValueError("--max-leakage-resample-attempts must be positive")

    return BuildOptions(
        output=args.output,
        max_samples=args.max_samples,
        min_context_words=args.min_context_words,
        max_context_words=args.max_context_words,
        seed=args.seed,
        split=args.split,
        source_mode=args.source_mode,
        gsm8k_jsonl=args.gsm8k_jsonl,
        wikipedia_jsonl=args.wikipedia_jsonl,
        tokenizer=args.tokenizer,
        max_leakage_resample_attempts=args.max_leakage_resample_attempts,
    )


def main() -> None:
    options = parse_args()
    rows = build_rows(options)
    validate_rows(rows)
    write_jsonl(rows, options.output)
    print(f"wrote {len(rows)} rows to {options.output}")
    print(f"source_mode={options.source_mode} split={options.split} seed={options.seed}")
    print(f"max_leakage_resample_attempts={options.max_leakage_resample_attempts}")
    print(f"context_words={[row['approximate_context_words'] for row in rows]}")
    print(f"leakage_resample_attempts={[row['leakage_resample_attempts'] for row in rows]}")


if __name__ == "__main__":
    main()
