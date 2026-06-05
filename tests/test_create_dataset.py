from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.create_dataset import (
    BuildOptions,
    _contains_answer,
    build_rows,
    validate_rows,
    write_jsonl,
)
from scripts.run_mvp import _select_prompt_items


def test_create_dataset_rows_match_fixture_runner_contract():
    rows = build_rows(
        BuildOptions(
            max_samples=2,
            min_context_words=120,
            max_context_words=180,
            seed=7,
        )
    )

    assert len(rows) == 2
    validate_rows(rows)

    for row in rows:
        assert row["source"] == "gsm8k+wikipedia"
        assert row["source_mode"] == "sample"
        assert row["domain"] == "math_augmented_wikipedia"
        assert row["question"] in row["prompt"]
        assert row["expected_answer"] == row["ground_truth_answer"] == row["answer"]
        assert row["expected_answer"] not in row["context"]
        assert row["expected_answer"] not in row["prompt"]
        assert row["augmentation_metadata"]["question_preserved"] is True
        assert row["augmentation_metadata"]["answer_in_distractor"] is False
        assert row["augmentation_metadata"]["answer_in_context"] is False
        assert row["augmentation_metadata"]["answer_in_prompt"] is False
        assert row["approximate_context_words"] >= 120
        assert row["token_length_metadata"]["token_count_method"] == "word_estimate"


def test_create_dataset_is_deterministic_with_fixed_seed():
    options = BuildOptions(max_samples=3, min_context_words=120, max_context_words=180, seed=99)

    first = build_rows(options)
    second = build_rows(options)

    assert first == second


def test_leakage_guard_detects_final_answer_as_token_or_phrase():
    assert _contains_answer("The total is 17 in this sentence.", "17") is True
    assert _contains_answer("The final amount is 31 dollars.", "31 dollars") is True
    assert _contains_answer("The year was 2017, not the answer.", "17") is False
    assert _contains_answer("No matching value appears here.", "17") is False
    assert _contains_answer("The force stayed active to at least 70000 personnel.", "70,000") is True
    assert _contains_answer("The force stayed active to at least 70,000 personnel.", "70000") is True


def test_validate_rows_rejects_answer_in_prompt():
    row = build_rows(BuildOptions(max_samples=1, min_context_words=120, max_context_words=180, seed=5))[0]
    row["prompt"] = row["prompt"] + f" {row['expected_answer']}"
    row["augmentation_metadata"]["answer_in_prompt"] = True

    try:
        validate_rows([row])
    except ValueError as exc:
        assert "answer leaked into model-visible prompt" in str(exc)
    else:
        raise AssertionError("validate_rows should reject prompt answer leakage")


def test_generated_dataset_is_compatible_with_fixture_runner(tmp_path: Path):
    output = tmp_path / "dataset.jsonl"
    rows = build_rows(BuildOptions(max_samples=2, min_context_words=120, max_context_words=180, seed=11))
    write_jsonl(rows, output)

    loaded = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert loaded == rows

    items = _select_prompt_items(prompt_source="fixture", n_prompts=3, fixture_path=output)

    assert [item.prompt_id for item in items] == [1, 2, 3]
    assert items[0].text == f"{rows[0]['context']}\n\n{rows[0]['question']}"
    assert items[0].metadata["fixture_id"] == rows[0]["id"]
    assert items[0].metadata["expected_answer"] == rows[0]["expected_answer"]
    assert items[2].metadata["fixture_id"] == rows[0]["id"]


def test_source_builder_resamples_wikipedia_passage_that_leaks_answer(tmp_path: Path):
    gsm8k = tmp_path / "gsm8k.jsonl"
    wikipedia = tmp_path / "wikipedia.jsonl"
    gsm8k.write_text(
        json.dumps(
            {
                "question": "A stadium sold 35,000 morning tickets and 35,000 evening tickets. How many tickets were sold?",
                "answer": "The total is 35000 + 35000 = 70000. #### 70,000",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    wikipedia.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "title": "Leaky passage",
                        "text": "The Canadian Armed Forces had active to at least 70000 personnel in one report.",
                    }
                ),
                json.dumps(
                    {
                        "title": "Clean passage",
                        "text": "Libraries organize books, reading rooms, catalog systems, local programs, and reference desks.",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows = build_rows(
        BuildOptions(
            max_samples=1,
            min_context_words=8,
            max_context_words=80,
            seed=3,
            source_mode="hf",
            gsm8k_jsonl=gsm8k,
            wikipedia_jsonl=wikipedia,
            max_leakage_resample_attempts=10,
        )
    )

    assert len(rows) == 1
    assert rows[0]["source_mode"] == "hf"
    assert rows[0]["expected_answer"] == "70,000"
    assert rows[0]["augmentation_metadata"]["answer_in_distractor"] is False
    assert rows[0]["augmentation_metadata"]["answer_in_context"] is False
    assert rows[0]["augmentation_metadata"]["answer_in_prompt"] is False
    assert rows[0]["skipped_due_to_leakage"] is False
    assert rows[0]["leakage_resample_attempts"] >= 1
    assert "Clean passage" in rows[0]["augmentation_metadata"]["distractor_titles"]
    validate_rows(rows)


def test_source_builder_skips_unsatisfiable_leaky_gsm8k_row(tmp_path: Path):
    gsm8k = tmp_path / "gsm8k.jsonl"
    wikipedia = tmp_path / "wikipedia.jsonl"
    gsm8k.write_text(
        json.dumps(
            {
                "question": "A final answer appears in every distractor. What is the answer?",
                "answer": "The answer is 70000. #### 70000",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    wikipedia.write_text(
        json.dumps({"title": "Always leaky", "text": "This passage repeats the answer 70,000 in prose."}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc:
        build_rows(
            BuildOptions(
                max_samples=1,
                min_context_words=4,
                max_context_words=40,
                seed=5,
                source_mode="hf",
                gsm8k_jsonl=gsm8k,
                wikipedia_jsonl=wikipedia,
                max_leakage_resample_attempts=2,
            )
        )

    message = str(exc.value)
    assert "requested sample count: 1" in message
    assert "generated clean row count: 0" in message
    assert "skipped GSM8K row count: 1" in message
    assert "leakage retry limit: 2" in message
