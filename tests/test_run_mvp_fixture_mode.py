from __future__ import annotations

import json
from pathlib import Path

from scripts.run_mvp import (
    PROMPTS,
    PromptMetrics,
    VramSnapshot,
    _generated_text_info,
    _print_summary,
    _prepare_cc_prompt,
    _select_prompt_items,
    _write_jsonl,
)


def _write_fixture(path: Path) -> None:
    rows = [
        {
            "id": "case_a",
            "domain": "finance",
            "context": "Alpha context with invoice details.",
            "question": "What is the invoice code?",
            "expected_answer": "INV-1",
            "evidence": "The invoice code is INV-1.",
            "approximate_context_words": 120,
        },
        {
            "id": "case_b",
            "domain": "ops",
            "context": "Beta context with shipment details.",
            "question": "How many boxes shipped?",
            "expected_answer": "14 boxes",
            "evidence": "The shipment included 14 boxes.",
            "approximate_context_words": 130,
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_select_prompt_items_defaults_to_smoke_prompts():
    items = _select_prompt_items(
        prompt_source="smoke",
        n_prompts=3,
        fixture_path=None,
    )

    assert [item.text for item in items] == PROMPTS[:3]
    assert [item.prompt_id for item in items] == [1, 2, 3]
    assert all(item.metadata == {} for item in items)
    assert all(item.context is None for item in items)
    assert all(item.question is None for item in items)


def test_select_prompt_items_loads_fixture_and_cycles_rows(tmp_path: Path):
    fixture = tmp_path / "fixture.jsonl"
    _write_fixture(fixture)

    items = _select_prompt_items(
        prompt_source="fixture",
        n_prompts=3,
        fixture_path=fixture,
    )

    assert [item.prompt_id for item in items] == [1, 2, 3]
    assert [item.metadata["fixture_id"] for item in items] == ["case_a", "case_b", "case_a"]
    assert items[0].text == "Alpha context with invoice details.\n\nWhat is the invoice code?"
    assert items[0].context == "Alpha context with invoice details."
    assert items[0].question == "What is the invoice code?"
    assert items[0].metadata == {
        "prompt_source": "fixture",
        "fixture_id": "case_a",
        "domain": "finance",
        "expected_answer": "INV-1",
        "evidence": "The invoice code is INV-1.",
        "approximate_context_words": 120,
    }


def test_fixture_prompt_metadata_can_be_added_to_cc_compression_info(tmp_path: Path):
    fixture = tmp_path / "fixture.jsonl"
    _write_fixture(fixture)
    item = _select_prompt_items(
        prompt_source="fixture",
        n_prompts=1,
        fixture_path=fixture,
    )[0]

    class FakeCompressor:
        model_name = "fake/model"

        def compress(self, context, question, keep_rate):
            assert context == item.context
            assert question == item.question
            return "compressed context\n\nWhat is the invoice code?", {
                "t_compress_ms": 10.0,
                "R_actual": 2.0,
                "N_original": 20,
                "N_compressed": 10,
                "keep_rate": keep_rate,
            }

    merged, info = _prepare_cc_prompt(
        item.question,
        FakeCompressor(),
        0.5,
        context=item.context,
    )
    info.update(item.metadata)

    assert merged == "compressed context\n\nWhat is the invoice code?"
    assert info["question_preserved"] is True
    assert info["fixture_id"] == "case_a"
    assert info["prompt_source"] == "fixture"


def test_summary_ignores_fixture_metadata_without_compression_fields(capsys):
    snapshot = VramSnapshot(
        label="after prompt",
        allocated_gib=1.0,
        reserved_gib=1.5,
        free_gib=6.0,
        total_gib=8.0,
    )
    metric = PromptMetrics(
        prompt_id=1,
        prompt_text="context\n\nquestion",
        input_tokens=10,
        output_tokens=2,
        generation_time_s=0.2,
        tok_per_s=10.0,
        acceptance_lengths=[1, 1],
        tau_mean=1.0,
        vram_after=snapshot,
        compression_info={"prompt_source": "fixture", "fixture_id": "case_a"},
    )

    _print_summary([metric], [snapshot])

    output = capsys.readouterr().out
    assert "average tok/s: 10.00" in output
    assert "average t_compress_ms" not in output


def test_generated_text_info_is_opt_in():
    class FakeTokenizer:
        def decode(self, token_ids, skip_special_tokens=True):
            assert token_ids == [7, 8]
            assert skip_special_tokens is True
            return "decoded answer"

    output_ids = [[1, 2, 7, 8]]

    assert _generated_text_info(FakeTokenizer(), output_ids, input_tokens=2, store_generated_text=False) == {}
    assert _generated_text_info(FakeTokenizer(), output_ids, input_tokens=2, store_generated_text=True) == {
        "generated_text": "decoded answer",
        "generated_token_count": 2,
    }


def test_write_jsonl_marks_baseline_ar_as_target_only(tmp_path: Path):
    snapshot = VramSnapshot(
        label="after prompt",
        allocated_gib=2.0,
        reserved_gib=2.5,
        free_gib=5.0,
        total_gib=8.0,
    )
    metric = PromptMetrics(
        prompt_id=1,
        prompt_text="prompt",
        input_tokens=10,
        output_tokens=3,
        generation_time_s=0.5,
        tok_per_s=6.0,
        acceptance_lengths=[],
        tau_mean=0.0,
        vram_after=snapshot,
        compression_info={"generation_mode": "autoregressive", "draft_used": False},
    )
    config = type(
        "Config",
        (),
        {
            "max_new_tokens": 32,
            "block_size": 16,
            "device": "cuda:0",
            "target_path": Path("models/Qwen3-4B"),
            "draft_path": Path("models/Qwen3-4B-DFlash-b16"),
            "tokenizer_path": Path("models/Qwen3-4B"),
        },
    )()
    output = tmp_path / "baseline_ar.jsonl"

    _write_jsonl(output, condition="Baseline-AR", backend_warning="sdpa", config=config, metrics=[metric])

    row = json.loads(output.read_text(encoding="utf-8"))
    assert row["condition"] == "Baseline-AR"
    assert row["compression"] == "none"
    assert row["keep_rate"] == 1.0
    assert row["generation_mode"] == "autoregressive"
    assert row["draft_used"] is False
    assert row["draft_path"] is None
    assert row["acceptance_lengths"] == []
    assert row["tau_mean"] == 0.0
