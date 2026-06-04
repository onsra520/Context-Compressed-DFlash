from __future__ import annotations

import json
from pathlib import Path

from scripts.run_mvp import (
    PROMPTS,
    PromptMetrics,
    VramSnapshot,
    _print_summary,
    _prepare_cc_prompt,
    _select_prompt_items,
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
