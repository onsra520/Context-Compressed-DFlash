from __future__ import annotations

import json
from pathlib import Path

from scripts.create_dataset import (
    BuildOptions,
    build_rows,
    validate_rows,
    write_jsonl,
)
from scripts.run_mvp import _select_prompt_items


def test_create_dataset_rows_match_fixture_runner_contract():
    rows = build_rows(
        BuildOptions(
            max_samples=2,
            seed=7,
        )
    )

    assert len(rows) == 2
    validate_rows(rows)

    for row in rows:
        assert row["source"] == "gsm8k"
        assert row["source_mode"] == "sample"
        assert row["domain"] == "numeric_qa"
        assert row["question"] in row["prompt"]
        assert row["expected_answer"] == row["ground_truth_answer"] == row["answer"]
        assert row["expected_answer"] not in row["context"]
        assert row["expected_answer"] not in row["prompt"]
        assert row["augmentation_metadata"]["question_preserved"] is True
        assert row["token_length_metadata"]["token_count_method"] == "word_estimate"


def test_create_dataset_is_deterministic_with_fixed_seed():
    options = BuildOptions(max_samples=3, seed=99)

    first = build_rows(options)
    second = build_rows(options)

    assert first == second


def test_generated_dataset_is_compatible_with_fixture_runner(tmp_path: Path):
    output = tmp_path / "dataset.jsonl"
    rows = build_rows(BuildOptions(max_samples=2, seed=11))
    write_jsonl(rows, output)

    loaded = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert loaded == rows

    items = _select_prompt_items(prompt_source="fixture", n_prompts=3, fixture_path=output)

    assert [item.prompt_id for item in items] == [1, 2, 3]
    assert items[0].text == f"{rows[0]['context']}\n\nQuestion: {rows[0]['question']}\n\nAnswer the question clearly. Format the final numeric answer after #### at the end."
    assert items[0].metadata["fixture_id"] == rows[0]["id"]
    assert items[0].metadata["expected_answer"] == rows[0]["expected_answer"]
    assert items[2].metadata["fixture_id"] == rows[0]["id"]
