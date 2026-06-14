from __future__ import annotations

import json
from pathlib import Path

from scripts.eval_datasets import load_eval_dataset, select_eval_dataset_rows, write_jsonl
from scripts.fetch_gsm8k_dataset import build_gsm8k_short_rows
from scripts.fetch_qmsum_meeting_qa_dataset import build_qmsum_eval_rows
from scripts.run_mvp import _select_prompt_items
from scripts.eval_datasets import (
    GSM8K_FINAL_ANSWER_INSTRUCTION,
    QMSUM_BALANCED_ANSWER_INSTRUCTION,
    QMSUM_EVIDENCE_FOCUSED_ANSWER_INSTRUCTION,
)


def test_build_gsm8k_short_rows_preserves_question_and_numeric_answer(tmp_path: Path):
    source = tmp_path / "gsm8k.jsonl"
    source.write_text(
        json.dumps(
            {
                "question": "A box has 4 red pens and 5 blue pens. How many pens are there?",
                "answer": "There are 4 + 5 = 9 pens. #### 9",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rows = build_gsm8k_short_rows(source_path=source, max_samples=1, seed=42, split="test")

    assert rows[0]["dataset_name"] == "gsm8k_short"
    assert rows[0]["expected_answer"] == "9"
    assert rows[0]["question"] in rows[0]["prompt"]
    assert "End with exactly one line:" in rows[0]["prompt"]
    assert rows[0]["prompt"].rstrip().endswith("Final answer: <number>")
    assert rows[0]["quality_policy"] == "numeric_extraction_exact_match_proxy"


def test_build_qmsum_eval_rows_flattens_meeting_qa_and_truncates_context():
    meetings = [
        {
            "idx": 7,
            "split": "test",
            "meeting_transcripts": [
                {"speaker": "A", "content": " ".join(["alpha"] * 40)},
                {"speaker": "B", "content": " ".join(["beta"] * 40)},
            ],
            "specific_query_list": [
                {"query": "What did the team discuss?", "answer": "The team discussed alpha and beta."}
            ],
        }
    ]

    rows = build_qmsum_eval_rows(
        meetings=meetings,
        max_samples=1,
        seed=42,
        min_context_words=10,
        max_context_words=25,
        split_label="test",
    )

    assert rows[0]["dataset_name"] == "qmsum_meeting_qa_long"
    assert rows[0]["expected_answer"] == "The team discussed alpha and beta."
    assert rows[0]["question"] in rows[0]["prompt"]
    assert rows[0]["approximate_context_words"] <= 25
    assert rows[0]["quality_policy"] == "normalized_text_containment_proxy"


def test_eval_dataset_registry_loads_and_samples_deterministically(tmp_path: Path):
    path = tmp_path / "gsm8k_eval.jsonl"
    rows = [
        {
            "id": f"gsm8k_short_test_{index:04d}",
            "dataset_name": "gsm8k_short",
            "context": "Short context.",
            "question": f"Question {index}?",
            "expected_answer": str(index),
            "prompt": f"Short context.\n\nQuestion {index}?",
            "domain": "numeric_qa",
            "evidence": "answer after marker",
            "approximate_context_words": 2,
            "quality_policy": "numeric_extraction_exact_match_proxy",
        }
        for index in range(1, 5)
    ]
    write_jsonl(rows, path)

    loaded = load_eval_dataset("gsm8k_short", path)
    first = select_eval_dataset_rows("gsm8k_short", n=3, seed=42, path=path)
    second = select_eval_dataset_rows("gsm8k_short", n=3, seed=42, path=path)

    assert len(loaded) == 4
    assert loaded[0].prompt.rstrip().endswith("Final answer: <number>")
    assert [row.id for row in first] == [row.id for row in second]
    assert len({row.id for row in first}) == 3


def test_run_mvp_gsm8k_dataset_items_keep_instruction_as_protected_suffix(tmp_path: Path):
    path = tmp_path / "gsm8k_eval.jsonl"
    write_jsonl(
        [
            {
                "id": "gsm8k_short_test_0001",
                "dataset_name": "gsm8k_short",
                "context": "Short context.",
                "question": "What is 6 + 7?",
                "expected_answer": "13",
                "prompt": "Short context.\n\nQuestion: What is 6 + 7?",
                "domain": "numeric_qa",
                "evidence": "answer after marker",
                "approximate_context_words": 2,
                "quality_policy": "numeric_extraction_exact_match_proxy",
            }
        ],
        path,
    )

    items = _select_prompt_items(
        prompt_source="dataset",
        n_prompts=1,
        fixture_path=None,
        dataset_name="gsm8k_short",
        dataset_path=path,
        seed=42,
    )

    assert items[0].text.rstrip().endswith("Final answer: <number>")
    assert items[0].question == "What is 6 + 7?"
    assert items[0].protected_suffix == GSM8K_FINAL_ANSWER_INSTRUCTION


def test_run_mvp_dataset_prompt_source_uses_registry_rows(tmp_path: Path):
    path = tmp_path / "qmsum_eval.jsonl"
    write_jsonl(
        [
            {
                "id": "qmsum_meeting_qa_test_0001",
                "dataset_name": "qmsum_meeting_qa_long",
                "context": "Speaker A: We approved the launch plan.",
                "question": "What was approved?",
                "expected_answer": "The launch plan was approved.",
                "prompt": "Meeting transcript:\nSpeaker A: We approved the launch plan.\n\nQuestion: What was approved?",
                "domain": "meeting_qa_long_context",
                "evidence": "QMSum reference answer",
                "approximate_context_words": 7,
                "quality_policy": "normalized_text_containment_proxy",
            }
        ],
        path,
    )

    items = _select_prompt_items(
        prompt_source="dataset",
        n_prompts=1,
        fixture_path=None,
        dataset_name="qmsum_meeting_qa_long",
        dataset_path=path,
        seed=42,
    )

    assert items[0].text.startswith("Meeting transcript:")
    assert items[0].context == "Speaker A: We approved the launch plan."
    assert items[0].question == "What was approved?"
    assert items[0].metadata["prompt_source"] == "dataset"
    assert items[0].metadata["dataset_name"] == "qmsum_meeting_qa_long"
    assert items[0].metadata["quality_policy"] == "normalized_text_containment_proxy"


def test_run_mvp_qmsum_dataset_items_keep_evidence_policy_as_protected_suffix(tmp_path: Path):
    path = tmp_path / "qmsum_eval.jsonl"
    write_jsonl(
        [
            {
                "id": "qmsum_meeting_qa_test_0002",
                "dataset_name": "qmsum_meeting_qa_long",
                "context": "Speaker A: The team approved the launch plan after budget review.",
                "question": "What did the team approve?",
                "expected_answer": "The team approved the launch plan.",
                "prompt": "Meeting transcript:\nSpeaker A: The team approved the launch plan after budget review.\n\nQuestion: What did the team approve?",
                "domain": "meeting_qa_long_context",
                "evidence": "QMSum reference answer",
                "approximate_context_words": 10,
                "quality_policy": "normalized_text_containment_proxy",
            }
        ],
        path,
    )

    items = _select_prompt_items(
        prompt_source="dataset",
        n_prompts=1,
        fixture_path=None,
        dataset_name="qmsum_meeting_qa_long",
        dataset_path=path,
        seed=42,
    )

    assert QMSUM_EVIDENCE_FOCUSED_ANSWER_INSTRUCTION in items[0].text
    assert "First focus on the exact evidence" in items[0].text
    assert "Do not answer from the general topic of the meeting." in items[0].text
    assert QMSUM_BALANCED_ANSWER_INSTRUCTION not in items[0].text
    assert "Answer concisely in 1-3 sentences." not in items[0].text
    assert "Final answer: <number>" not in items[0].text
    assert items[0].question == "What did the team approve?"
    assert items[0].protected_suffix == QMSUM_EVIDENCE_FOCUSED_ANSWER_INSTRUCTION
