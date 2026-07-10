from __future__ import annotations

import json
from pathlib import Path

import pytest
import torch

from ccdf.compression.llmlingua import LLMLinguaCompressor
from scripts.run_mvp import (
    PROMPTS,
    BENCHMARK_PROTOCOL_VERSION,
    PromptMetrics,
    VramSnapshot,
    _generated_text_info,
    _load_jsonl_rows,
    _measure_target_prefill,
    _metric_to_row,
    _print_summary,
    _prepare_cc_prompt,
    _prepare_output_state,
    _read_config,
    _select_prompt_items,
    _write_jsonl_row,
    _write_jsonl,
)


class ExpandingTokenizer:
    model_max_length = 512

    def encode(self, text, add_special_tokens=False):
        token_ids = []
        for word in str(text).split():
            width = 5 if word.startswith("wide") else 1
            token_ids.extend([word] * width)
        return token_ids


def _fake_config():
    return type(
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


def _fake_metric(prompt_id: int, *, compression_info: dict | None = None) -> PromptMetrics:
    snapshot = VramSnapshot(
        label=f"after prompt {prompt_id}",
        allocated_gib=2.0 + prompt_id,
        reserved_gib=2.5 + prompt_id,
        free_gib=5.0,
        total_gib=8.0,
    )
    return PromptMetrics(
        prompt_id=prompt_id,
        prompt_text=f"prompt {prompt_id}",
        input_tokens=10 + prompt_id,
        output_tokens=3,
        generation_time_s=0.5,
        tok_per_s=6.0,
        acceptance_lengths=[],
        tau_mean=0.0,
        vram_after=snapshot,
        compression_info=compression_info or {},
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


def test_read_config_keeps_default_clamp_but_accepts_cli_override(tmp_path: Path):
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        "\n".join(
            [
                "model:",
                "  target_id: models/Qwen3-4B",
                "  draft_id: models/Qwen3-4B-DFlash-b16",
                "  tokenizer_id: models/Qwen3-4B",
                "runtime:",
                "  device: cuda:0",
                "benchmark:",
                "  block_size: 16",
                "  max_new_tokens: 256",
                "  temperature: 0.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert _read_config(config_path).max_new_tokens == 32
    assert _read_config(config_path, max_new_tokens_override=128).max_new_tokens == 128


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


def test_fixture_prompt_can_use_token_chunked_llmlingua_wrapper_without_over_budget_call(
    monkeypatch,
    tmp_path: Path,
):
    tokenizer = ExpandingTokenizer()
    rows = [
        {
            "id": "long_case",
            "domain": "math",
            "context": " ".join(f"wide{i}" for i in range(180)),
            "question": "What value must stay protected?",
            "expected_answer": "42",
            "evidence": "The protected value is 42.",
            "approximate_context_words": 180,
        }
    ]
    fixture = tmp_path / "long_fixture.jsonl"
    fixture.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    item = _select_prompt_items(
        prompt_source="fixture",
        n_prompts=1,
        fixture_path=fixture,
    )[0]
    calls = []

    class FakePromptCompressor:
        def __init__(self, model_name, device_map, use_llmlingua2, llmlingua2_config):
            self.tokenizer = tokenizer

        def compress_prompt(self, context, question="", rate=0.5, concate_question=True, **kwargs):
            token_count = len(tokenizer.encode(context[0], add_special_tokens=False))
            if token_count > 90:
                raise AssertionError(f"over-budget chunk reached compressor: {token_count}")
            calls.append(token_count)
            words = context[0].split()
            compressed_words = words[: max(1, len(words) // 2)]
            return {
                "compressed_prompt": " ".join(compressed_words),
                "origin_tokens": token_count,
                "compressed_tokens": len(tokenizer.encode(" ".join(compressed_words), add_special_tokens=False)),
            }

    monkeypatch.setattr("ccdf.compression.llmlingua.PromptCompressor", FakePromptCompressor)

    compressor = LLMLinguaCompressor(max_context_tokens_per_chunk=90)
    merged, info = _prepare_cc_prompt(
        item.question,
        compressor,
        0.5,
        context=item.context,
    )

    assert item.question in merged
    assert info["question_preserved"] is True
    assert info["compressor_chunked"] is True
    assert info["compressor_chunk_count"] == len(calls)
    assert info["compressor_chunking_mode"] == "tokenizer"
    assert info["compressor_chunk_token_budget"] == 90
    assert info["compressor_chunk_max_observed_tokens"] <= 90
    assert max(calls) <= 90


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


def test_measure_target_prefill_is_cpu_safe():
    calls = []

    class FakeTarget:
        def __call__(self, **kwargs):
            calls.append(kwargs)
            return object()

    input_ids = torch.tensor([[1, 2, 3]])

    measurement = _measure_target_prefill(FakeTarget(), input_ids, device="cpu")

    assert measurement.elapsed_ms >= 0.0
    assert measurement.mode == "cpu_timer"
    assert measurement.vram_allocated_gib is None
    assert measurement.vram_reserved_gib is None
    assert calls[0]["input_ids"] is input_ids
    assert calls[0]["attention_mask"].tolist() == [[1, 1, 1]]
    assert calls[0]["use_cache"] is True


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
    assert row["t_prefill_ms"] == 0.0
    assert row["t_prefill_mode"] == "not_measured"
    assert row["prefill_vram_allocated_gib"] is None
    assert row["prefill_vram_reserved_gib"] is None


def test_metric_row_keeps_dflash_timing_breakdown_without_extra_prefill():
    metric = _fake_metric(1)
    metric.generation_details = {
        "target_prefill_ms": 120.0,
        "draft_prefill_ms": 8.0,
        "draft_proposal_ms": 42.0,
        "target_verification_ms": 310.0,
        "verification_call_count": 4,
        "draft_tokens_proposed": 60,
        "accepted_tokens": 10,
        "accepted_tokens_per_verification": 2.5,
        "rejection_or_rollback_count": 3,
        "rollback_tokens": 50,
        "cache_management_ms": None,
        "synchronization_overhead_ms": None,
    }
    metric.t_prefill_ms = 0.0
    metric.t_prefill_mode = "included_in_generation"

    row = _metric_to_row(
        metric,
        condition="DFlash-R1",
        backend_warning="sdpa",
        config=_fake_config(),
    )

    assert row["t_e2e_ms"] == row["t_generation_ms"]
    assert row["t_prefill_mode"] == "included_in_generation"
    assert row["target_prefill_ms"] == 120.0
    assert row["verification_call_count"] == 4
    assert row["rollback_tokens"] == 50


def test_metric_to_row_adds_protocol_metadata_and_keeps_legacy_fields(tmp_path: Path):
    metric = _fake_metric(
        2,
        compression_info={
            "compression": "llmlingua",
            "R_actual": 2.0,
            "t_compress_ms": 10.0,
            "compressor_chunking_mode": "tokenizer",
        },
    )
    output = tmp_path / "rows.jsonl"

    row = _metric_to_row(
        metric,
        condition="LLMLingua-AR-R2",
        backend_warning="sdpa",
        config=_fake_config(),
        benchmark_prompt_index=7,
        warmup_prompts=1,
        resume_enabled=True,
        resumed_from_rows=3,
        output_write_mode="append_resume",
        output_path=output,
    )

    assert row["benchmark_prompt_index"] == 7
    assert row["is_warmup"] is False
    assert row["warmup_prompts"] == 1
    assert row["resume_enabled"] is True
    assert row["resumed_from_rows"] == 3
    assert row["output_write_mode"] == "append_resume"
    assert row["benchmark_protocol_version"] == BENCHMARK_PROTOCOL_VERSION
    assert row["tok_per_sec"] == row["tokens_per_second"] == 6.0
    assert row["output_path"] == str(output)
    assert row["compressor_chunking_mode"] == "tokenizer"


def test_prepare_output_state_prevents_silent_overwrite(tmp_path: Path):
    output = tmp_path / "existing.jsonl"
    output.write_text("{}\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Use --resume"):
        _prepare_output_state(
            output,
            condition="DFlash-R1",
            n_prompts=1,
            resume=False,
            overwrite=False,
        )


def test_prepare_output_state_rejects_resume_and_overwrite_together(tmp_path: Path):
    with pytest.raises(ValueError, match="cannot be used together"):
        _prepare_output_state(
            tmp_path / "rows.jsonl",
            condition="DFlash-R1",
            n_prompts=1,
            resume=True,
            overwrite=True,
        )


def test_incremental_jsonl_remains_valid_after_simulated_failure(tmp_path: Path):
    output = tmp_path / "partial.jsonl"
    config = _fake_config()

    with output.open("w", encoding="utf-8") as handle:
        for prompt_index in range(1, 3):
            row = _metric_to_row(
                _fake_metric(prompt_index),
                condition="DFlash-R1",
                backend_warning="sdpa",
                config=config,
                benchmark_prompt_index=prompt_index,
                output_path=output,
            )
            _write_jsonl_row(handle, row)
        try:
            raise RuntimeError("simulated stop after two prompts")
        except RuntimeError:
            pass

    rows = _load_jsonl_rows(output)

    assert len(rows) == 2
    assert [row["benchmark_prompt_index"] for row in rows] == [1, 2]
    assert all(row["is_warmup"] is False for row in rows)


def test_resume_state_skips_completed_rows_and_appends_remaining_without_duplicates(tmp_path: Path):
    output = tmp_path / "resume.jsonl"
    config = _fake_config()
    first_row = _metric_to_row(
        _fake_metric(1),
        condition="LLMLingua-AR-R2",
        backend_warning="sdpa",
        config=config,
        benchmark_prompt_index=1,
        output_path=output,
    )
    with output.open("w", encoding="utf-8") as handle:
        _write_jsonl_row(handle, first_row)

    state = _prepare_output_state(
        output,
        condition="LLMLingua-AR-R2",
        n_prompts=3,
        resume=True,
        overwrite=False,
    )

    assert state.completed_prompt_indexes == {1}
    assert state.write_mode == "append_resume"
    assert state.resumed_from_rows == 1

    with output.open("a", encoding="utf-8") as handle:
        for prompt_index in range(1, 4):
            if prompt_index in state.completed_prompt_indexes:
                continue
            row = _metric_to_row(
                _fake_metric(prompt_index),
                condition="LLMLingua-AR-R2",
                backend_warning="sdpa",
                config=config,
                benchmark_prompt_index=prompt_index,
                resume_enabled=state.resume_enabled,
                resumed_from_rows=state.resumed_from_rows,
                output_write_mode=state.write_mode,
                output_path=output,
            )
            _write_jsonl_row(handle, row)

    rows = _load_jsonl_rows(output)

    assert len(rows) == 3
    assert [row["benchmark_prompt_index"] for row in rows] == [1, 2, 3]
    assert len({row["benchmark_prompt_index"] for row in rows}) == 3
    assert rows[1]["resume_enabled"] is True
    assert rows[1]["resumed_from_rows"] == 1


def test_resume_state_rejects_duplicate_prompt_indexes(tmp_path: Path):
    output = tmp_path / "dupe.jsonl"
    config = _fake_config()
    row = _metric_to_row(
        _fake_metric(1),
        condition="DFlash-R1",
        backend_warning="sdpa",
        config=config,
        benchmark_prompt_index=1,
        output_path=output,
    )
    output.write_text(
        json.dumps(row) + "\n" + json.dumps(row) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate"):
        _prepare_output_state(
            output,
            condition="DFlash-R1",
            n_prompts=3,
            resume=True,
            overwrite=False,
        )


def test_warmup_rows_are_not_written_to_measured_artifact(tmp_path: Path):
    output = tmp_path / "warmup.jsonl"
    config = _fake_config()
    warmup_metric = _fake_metric(99)
    measured_metric = _fake_metric(1)

    with output.open("w", encoding="utf-8") as handle:
        # Simulate a successful warm-up by intentionally not writing warmup_metric.
        assert warmup_metric.prompt_id == 99
        row = _metric_to_row(
            measured_metric,
            condition="Baseline-AR",
            backend_warning="sdpa",
            config=config,
            benchmark_prompt_index=1,
            warmup_prompts=1,
            output_path=output,
        )
        _write_jsonl_row(handle, row)

    rows = _load_jsonl_rows(output)

    assert len(rows) == 1
    assert rows[0]["prompt_id"] == 1
    assert rows[0]["warmup_prompts"] == 1
    assert rows[0]["is_warmup"] is False
