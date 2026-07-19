import copy
import json
from pathlib import Path

import pytest

from ccdf.config import load_config
from ccdf.datasets.pipeline import GSM8K_INSTRUCTION, build_samples, load_canonical_samples
from ccdf.datasets.qmsum_context import build_speaker_chunks, select_query_aware_context
from ccdf.datasets.schema import validate_sample, validate_samples
from ccdf.evaluation import evaluate_dataset_output


def _selection() -> dict:
    return {
        "seed": 42,
        "gsm8k": [{"upstream_row_index": 0}],
        "qmsum": [{"meeting_index": 0, "query_index": 0}],
    }


def test_gsm8k_conversion_is_stable_and_reference_is_numeric() -> None:
    raw = [{"question": "What is 2 + 3?", "answer": "Work.\n#### 5"}]
    first = build_samples(raw, _selection(), "gsm8k")
    second = build_samples(copy.deepcopy(raw), _selection(), "gsm8k")

    assert first == second
    assert first[0]["reference"] == "5"
    assert first[0]["sample_id"].startswith("gsm8k-test-000000-")
    assert first[0]["metadata"]["instruction"] == GSM8K_INSTRUCTION
    assert load_config("config.yml").require("prompts.gsm8k_instruction") == GSM8K_INSTRUCTION
    assert first[0]["prompt"] == f"Math word problem:\nWhat is 2 + 3?\n\n{GSM8K_INSTRUCTION}"
    assert first[0]["prompt_version"] == "stage3-gsm8k-calculation-v5"
    validate_samples(first, expected_dataset="gsm8k", expected_split="test", expected_count=1)


def test_qmsum_conversion_selects_query_aware_context_with_accounting() -> None:
    raw = [
        {
            "meeting_transcripts": [
                {"speaker": "A", "content": "First point."},
                {"speaker": "B", "content": "Second point."},
            ],
            "specific_query_list": [{"query": "What happened?", "answer": "Two points."}],
        }
    ]
    sample = build_samples(raw, _selection(), "qmsum")[0]

    assert sample["context"] == "A: First point.\nB: Second point."
    accounting = sample["metadata"]["context_selection"]
    assert accounting["policy"] == "query_aware_budgeted"
    assert accounting["selected_context_token_count"] <= accounting["budget_tokens"]
    assert accounting["selected_context_sha256"]
    assert "reference_overlap_diagnostic" in accounting
    validate_sample(sample)


def test_qmsum_selection_is_token_budgeted_and_turn_bounded() -> None:
    long_turns = [
        {"speaker": f"S{index}", "content": " ".join([f"word{index}"] * 400)}
        for index in range(5)
    ]
    raw = [
        {
            "meeting_transcripts": long_turns,
            "specific_query_list": [{"query": "Summary?", "answer": "Reference."}],
        }
    ]
    sample = build_samples(raw, _selection(), "qmsum")[0]
    accounting = sample["metadata"]["context_selection"]

    assert accounting["selected_context_token_count"] <= accounting["budget_tokens"] == 1000
    assert len(accounting["selected_chunk_ids"]) < accounting["full_chunk_count"]
    ranges = accounting["selected_source_ranges"]
    assert ranges == sorted(ranges, key=lambda row: row["start_turn"])


def test_qmsum_chunking_scoring_and_tie_break_are_deterministic() -> None:
    turns = [
        {"speaker": "A", "content": "unrelated opening"},
        {"speaker": "B", "content": "budget decision was twenty"},
        {"speaker": "C", "content": "budget decision was thirty"},
    ]
    count = lambda text: len(text.split())
    first = select_query_aware_context(
        turns, "What was the budget decision?", count, budget_tokens=6, chunk_target_tokens=4
    )
    second = select_query_aware_context(
        copy.deepcopy(turns), "What was the budget decision?", count,
        budget_tokens=6, chunk_target_tokens=4,
    )
    assert first == second
    assert first[1]["selected_chunk_ids"] == ["chunk-0001"]
    assert first[1]["selected_context_token_count"] <= 6


def test_qmsum_selection_reorders_ranked_chunks_to_source_order() -> None:
    turns = [
        {"speaker": "A", "content": "alpha detail"},
        {"speaker": "B", "content": "irrelevant"},
        {"speaker": "C", "content": "alpha alpha decision"},
    ]
    context, evidence = select_query_aware_context(
        turns, "alpha decision", lambda text: len(text.split()),
        budget_tokens=7, chunk_target_tokens=3,
    )
    assert evidence["selected_source_ranges"] == sorted(
        evidence["selected_source_ranges"], key=lambda row: row["start_turn"]
    )
    assert context.index("A:") < context.index("C:")


def test_qmsum_selector_api_has_no_reference_input() -> None:
    import inspect

    assert "reference" not in inspect.signature(select_query_aware_context).parameters


def test_speaker_chunks_preserve_whole_utterances() -> None:
    turns = [{"speaker": "A", "content": "one two"}, {"speaker": "B", "content": "three four"}]
    chunks = build_speaker_chunks(turns, lambda text: len(text.split()), target_tokens=4)
    assert "A: one two" in "\n".join(chunk.text for chunk in chunks)
    assert "B: three four" in "\n".join(chunk.text for chunk in chunks)


def test_canonical_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    raw = [{"question": "What is 2 + 3?", "answer": "#### 5"}]
    row = build_samples(raw, _selection(), "gsm8k")[0]
    path = tmp_path / "samples.jsonl"
    path.write_text("\n".join(json.dumps(row) for _ in range(2)) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate canonical sample IDs"):
        load_canonical_samples(path, expected_dataset="gsm8k")


def test_gsm8k_parser_is_anchored_and_does_not_use_substring_matching() -> None:
    sample = build_samples(
        [{"question": "What is 2 + 3?", "answer": "#### 5"}], _selection(), "gsm8k"
    )[0]
    correct = evaluate_dataset_output(sample, "Reasoning 15 is irrelevant.\nFinal answer: 5")
    malformed = evaluate_dataset_output(sample, "The answer contains 5, but has no final line.")
    inline = evaluate_dataset_output(sample, "Calculation: 2 + 3 = 5. Final answer: 5.")

    assert correct["parser_status"] == "parsed"
    assert correct["quality_score"] == 1.0
    assert malformed["parser_status"] == "missing_final_answer_line"
    assert malformed["quality_score"] == 0.0
    assert inline["parser_status"] == "parsed"
    assert inline["parsed_answer"] == "5"


def test_qmsum_rouge_l_is_order_sensitive_and_not_semantic_claim() -> None:
    sample = build_samples(
        [
            {
                "meeting_transcripts": [{"speaker": "A", "content": "Discussion."}],
                "specific_query_list": [{"query": "Summary?", "answer": "alpha beta gamma"}],
            }
        ],
        _selection(),
        "qmsum",
    )[0]
    result = evaluate_dataset_output(sample, "alpha gamma")

    assert result["quality_score"] == pytest.approx(0.8)
    assert result["details"]["semantic_correctness"] == "NOT_CLAIMED"
