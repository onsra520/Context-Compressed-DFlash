from __future__ import annotations

from pathlib import Path

import pytest

from ccdf.compression import PassthroughCompressor, merge, segment_gsm8k
from ccdf.compression.llmlingua import LLMLinguaCompressor

from scripts.run_mvp import (
    PromptMetrics,
    SmokeConfig,
    VramSnapshot,
    _condition_keep_rate,
    _is_ar_condition,
    _metric_to_row,
    _parse_keep_rate_percent,
    _prepare_cc_prompt,
    _resolve_keep_rate,
)
from scripts.eval_datasets import (
    GSM8K_FINAL_ANSWER_INSTRUCTION,
    QMSUM_BALANCED_ANSWER_INSTRUCTION,
    QMSUM_EVIDENCE_FOCUSED_ANSWER_INSTRUCTION,
)


class ExpandingTokenizer:
    model_max_length = 512

    def __init__(self, *, wide_multiplier: int = 4):
        self.wide_multiplier = wide_multiplier

    def encode(self, text, add_special_tokens=False):
        token_ids = []
        for word in str(text).split():
            width = self.wide_multiplier if word.startswith("wide") else 1
            token_ids.extend([word] * width)
        return token_ids


class CharTokenizer:
    model_max_length = 512

    def encode(self, text, add_special_tokens=False):
        return list(str(text))


def test_passthrough_compressor_returns_original_context():
    compressor = PassthroughCompressor()
    text, info = compressor.compress("context", "question", 1.0)
    assert text == "context"
    assert info == {
        "t_compress_ms": 0.0,
        "R_actual": 1.0,
        "N_original": len("context"),
        "N_compressed": len("context"),
        "keep_rate": 1.0,
        "strategy": "passthrough",
    }


def test_segment_and_merge_gsm8k_prompt():
    prompt = "context block\n\nWhat is 2 + 2?"
    segmented = segment_gsm8k(prompt)
    assert segmented.context == "context block"
    assert segmented.question == "What is 2 + 2?"
    assert merge(segmented.context, segmented.question) == "context block\n\nWhat is 2 + 2?"


def test_llmlingua_compressor_merges_original_question_and_reports_metadata(monkeypatch):
    captured = {}
    tokenizer = ExpandingTokenizer(wide_multiplier=1)

    class FakePromptCompressor:
        def __init__(self, model_name, device_map, use_llmlingua2, llmlingua2_config):
            self.tokenizer = tokenizer
            captured["init"] = {
                "model_name": model_name,
                "device_map": device_map,
                "use_llmlingua2": use_llmlingua2,
                "llmlingua2_config": llmlingua2_config,
            }

        def compress_prompt(self, context, question="", rate=0.5, concate_question=True, **kwargs):
            captured["call"] = {
                "context": context,
                "question": question,
                "rate": rate,
                "concate_question": concate_question,
                "kwargs": kwargs,
            }
            return {
                "compressed_prompt": "shortened context",
                "origin_tokens": 20,
                "compressed_tokens": 8,
                "ratio": "2.5x",
                "rate": "40.0%",
            }

    monkeypatch.setattr("ccdf.compression.llmlingua.PromptCompressor", FakePromptCompressor)

    compressor = LLMLinguaCompressor()
    merged_text, info = compressor.compress(
        context="Long supporting context that should shrink.",
        question="What is 7 + 5?",
        keep_rate=0.4,
    )

    assert merged_text == "shortened context\n\nWhat is 7 + 5?"
    assert info["N_original"] == 20
    assert info["N_compressed"] == 8
    assert info["R_actual"] == pytest.approx(2.5)
    assert info["t_compress_ms"] >= 0.0
    assert info["keep_rate"] == pytest.approx(0.4)
    assert info["strategy"] == "llmlingua-2"
    assert captured["init"]["device_map"] == "cpu"
    assert captured["init"]["use_llmlingua2"] is True
    assert captured["call"]["context"] == ["Long supporting context that should shrink."]
    assert captured["call"]["question"] == "What is 7 + 5?"
    assert captured["call"]["concate_question"] is False
    assert info["compressor_chunked"] is False
    assert info["compressor_chunk_count"] == 1
    assert info["compressor_chunking_mode"] == "tokenizer"
    assert info["compressor_chunk_token_budget"] > 0
    assert info["compressor_chunk_max_observed_tokens"] <= info["compressor_chunk_token_budget"]
    assert info["compressor_chunk_encoder_max_length"] == 512
    assert info["compressor_chunk_safety_margin"] > 0
    assert info["compressor_chunk_backend_calls"] == 1


def test_prepare_cc_prompt_adds_capped_audit_previews(monkeypatch):
    tokenizer = ExpandingTokenizer(wide_multiplier=1)

    class FakePromptCompressor:
        def __init__(self, model_name, device_map, use_llmlingua2, llmlingua2_config):
            self.tokenizer = tokenizer

        def compress_prompt(self, context, question="", rate=0.5, concate_question=True, **kwargs):
            return {
                "compressed_prompt": "compressed context with key numbers",
                "origin_tokens": 100,
                "compressed_tokens": 40,
            }

    monkeypatch.setattr("ccdf.compression.llmlingua.PromptCompressor", FakePromptCompressor)

    context = " ".join(f"context-token-{index}" for index in range(200))
    question = "What is the final value?"
    compressor = LLMLinguaCompressor()

    merged_prompt, info = _prepare_cc_prompt(question, compressor, keep_rate=0.5, context=context)

    assert question in merged_prompt
    assert info["compression_ratio"] == pytest.approx(2.5)
    assert info["actual_compression_ratio"] == pytest.approx(2.5)
    assert info["original_input_tokens"] == 100
    assert info["compressed_input_tokens"] == 40
    assert info["question_preserved"] is True
    assert info["original_context_preview"].startswith("context-token-0")
    assert info["compressed_context_preview"] == "compressed context with key numbers"
    assert info["original_prompt_preview"].startswith("context-token-0")
    assert info["compressed_prompt_preview"].endswith(question)
    assert len(info["original_context_preview"]) <= 243
    assert len(info["compressed_prompt_preview"]) <= 243


def test_prepare_cc_prompt_appends_protected_suffix_outside_compression(monkeypatch):
    captured = {}
    tokenizer = ExpandingTokenizer(wide_multiplier=1)

    class FakePromptCompressor:
        def __init__(self, model_name, device_map, use_llmlingua2, llmlingua2_config):
            self.tokenizer = tokenizer

        def compress_prompt(self, context, question="", rate=0.5, concate_question=True, **kwargs):
            captured["question"] = question
            captured["context"] = context
            compressed_context = " ".join(f"compressed-token-{index}" for index in range(120))
            return {
                "compressed_prompt": compressed_context,
                "origin_tokens": 50,
                "compressed_tokens": 25,
            }

    monkeypatch.setattr("ccdf.compression.llmlingua.PromptCompressor", FakePromptCompressor)

    question = "What is 6 + 7?"
    compressor = LLMLinguaCompressor()

    merged_prompt, info = _prepare_cc_prompt(
        question,
        compressor,
        keep_rate=0.5,
        context="Original GSM8K context",
        protected_suffix=GSM8K_FINAL_ANSWER_INSTRUCTION,
    )

    assert captured["question"] == question
    assert merged_prompt.startswith("compressed-token-0 compressed-token-1")
    assert merged_prompt.endswith(f"{question}\n\n{GSM8K_FINAL_ANSWER_INSTRUCTION}")
    assert info["question_preserved"] is True
    assert info["protected_suffix_preserved"] is True
    assert info["protected_suffix_preview"] == GSM8K_FINAL_ANSWER_INSTRUCTION.replace("\n", " ")
    assert "Final answer: <number>" in info["final_prompt_preview"]
    assert "Final answer: <number>" in info["final_prompt_tail_preview"]
    assert info["compressed_prompt_preview"] == info["final_prompt_preview"]
    assert len(info["final_prompt_preview"]) <= 243


def test_prepare_cc_prompt_preserves_qmsum_balanced_policy_metadata(monkeypatch):
    captured = {}
    tokenizer = ExpandingTokenizer(wide_multiplier=1)

    class FakePromptCompressor:
        def __init__(self, model_name, device_map, use_llmlingua2, llmlingua2_config):
            self.tokenizer = tokenizer

        def compress_prompt(self, context, question="", rate=0.5, concate_question=True, **kwargs):
            captured["question"] = question
            captured["context"] = context
            return {
                "compressed_prompt": "compressed meeting context",
                "origin_tokens": 80,
                "compressed_tokens": 40,
            }

    monkeypatch.setattr("ccdf.compression.llmlingua.PromptCompressor", FakePromptCompressor)

    question = "What did the team approve?"
    compressor = LLMLinguaCompressor()

    merged_prompt, info = _prepare_cc_prompt(
        question,
        compressor,
        keep_rate=0.5,
        context="Original meeting context",
        protected_suffix=QMSUM_BALANCED_ANSWER_INSTRUCTION,
    )

    assert captured["question"] == question
    assert merged_prompt.endswith(f"{question}\n\n{QMSUM_BALANCED_ANSWER_INSTRUCTION}")
    assert info["question_preserved"] is True
    assert info["protected_suffix_preserved"] is True
    assert info["qmsum_answer_policy_enabled"] is True
    assert info["qmsum_answer_policy_type"] == "balanced"
    assert info["qmsum_answer_policy_preserved"] is True
    assert info["qmsum_output_policy_preview"].startswith("Answer in 3-6 concise sentences.")
    assert "key entities, decisions, reasons" in info["qmsum_output_policy_preview"]
    assert "supported by the meeting context." in info["final_prompt_tail_preview"]
    assert "Answer concisely in 1-3 sentences." not in info["final_prompt_tail_preview"]
    assert "Final answer: <number>" not in info["final_prompt_tail_preview"]


def test_prepare_cc_prompt_preserves_qmsum_evidence_policy_metadata(monkeypatch):
    captured = {}
    tokenizer = ExpandingTokenizer(wide_multiplier=1)

    class FakePromptCompressor:
        def __init__(self, model_name, device_map, use_llmlingua2, llmlingua2_config):
            self.tokenizer = tokenizer

        def compress_prompt(self, context, question="", rate=0.5, concate_question=True, **kwargs):
            captured["question"] = question
            captured["context"] = context
            return {
                "compressed_prompt": "compressed meeting context with project evidence",
                "origin_tokens": 100,
                "compressed_tokens": 50,
            }

    monkeypatch.setattr("ccdf.compression.llmlingua.PromptCompressor", FakePromptCompressor)

    question = "What did the team approve?"
    compressor = LLMLinguaCompressor()

    merged_prompt, info = _prepare_cc_prompt(
        question,
        compressor,
        keep_rate=0.5,
        context="Original meeting context",
        protected_suffix=QMSUM_EVIDENCE_FOCUSED_ANSWER_INSTRUCTION,
    )

    assert captured["question"] == question
    assert merged_prompt.endswith(f"{question}\n\n{QMSUM_EVIDENCE_FOCUSED_ANSWER_INSTRUCTION}")
    assert info["question_preserved"] is True
    assert info["protected_suffix_preserved"] is True
    assert info["qmsum_answer_policy_enabled"] is True
    assert info["qmsum_answer_policy_type"] == "evidence_focused"
    assert info["qmsum_answer_policy_preserved"] is True
    assert info["qmsum_evidence_focus_enabled"] is True
    assert info["qmsum_evidence_focus_version"] == "task77"
    assert "First focus on the exact evidence" in info["qmsum_output_policy_preview"]
    assert "Do not answer from the general topic" in info["final_prompt_tail_preview"]
    assert "Answer in 3-6 concise sentences." not in info["final_prompt_tail_preview"]
    assert "Final answer: <number>" not in info["final_prompt_tail_preview"]


def test_non_compressed_rows_do_not_claim_compression_preview_metadata():
    metric = PromptMetrics(
        prompt_id=1,
        prompt_text="Prompt",
        input_tokens=4,
        output_tokens=2,
        generation_time_s=0.5,
        tok_per_s=4.0,
        acceptance_lengths=[],
        tau_mean=0.0,
        vram_after=VramSnapshot("after", 1.0, 2.0, 3.0, 4.0),
    )
    config = SmokeConfig(
        target_path=Path("target"),
        draft_path=Path("draft"),
        tokenizer_path=Path("tokenizer"),
        device="cpu",
        block_size=16,
        max_new_tokens=128,
        temperature=0.0,
        raw_config={},
    )

    row = _metric_to_row(
        metric,
        condition="Baseline-AR",
        backend_warning="",
        config=config,
    )

    assert row["compression"] == "none"
    assert row["keep_rate"] == 1.0
    assert "compressed_prompt_preview" not in row
    assert "compressed_context_preview" not in row
    assert "original_prompt_preview" not in row


def test_llmlingua_compressor_chunks_by_token_budget_and_preserves_question(monkeypatch):
    calls = []
    tokenizer = ExpandingTokenizer(wide_multiplier=4)

    class FakePromptCompressor:
        def __init__(self, model_name, device_map, use_llmlingua2, llmlingua2_config):
            self.tokenizer = tokenizer

        def compress_prompt(self, context, question="", rate=0.5, concate_question=True, **kwargs):
            chunk = context[0]
            token_count = len(tokenizer.encode(chunk, add_special_tokens=False))
            if token_count > 128:
                raise AssertionError(f"chunk too long: {token_count}")
            calls.append(
                {
                    "chunk": chunk,
                    "tokens": token_count,
                    "question": question,
                    "rate": rate,
                    "concate_question": concate_question,
                }
            )
            words = chunk.split()
            compressed_words = words[: max(1, len(words) // 2)]
            return {
                "compressed_prompt": " ".join(compressed_words),
                "origin_tokens": token_count,
                "compressed_tokens": len(tokenizer.encode(" ".join(compressed_words), add_special_tokens=False)),
            }

    monkeypatch.setattr("ccdf.compression.llmlingua.PromptCompressor", FakePromptCompressor)

    context = " ".join(f"wide{i}" for i in range(260))
    question = "What is the protected question?"
    compressor = LLMLinguaCompressor(max_context_tokens_per_chunk=128)

    merged_text, info = compressor.compress(context=context, question=question, keep_rate=0.5)

    assert question in merged_text
    assert len(calls) > 3
    assert max(call["tokens"] for call in calls) <= 128
    assert all(call["question"] == question for call in calls)
    assert all(call["rate"] == pytest.approx(0.5) for call in calls)
    assert all(call["concate_question"] is False for call in calls)
    assert info["N_original"] == 1040
    assert info["N_compressed"] <= info["N_original"]
    assert info["R_actual"] >= 1.0
    assert info["compressor_chunked"] is True
    assert info["compressor_chunk_count"] == len(calls)
    assert info["compressor_chunking_mode"] == "tokenizer"
    assert info["compressor_chunk_token_budget"] == 128
    assert info["compressor_chunk_max_observed_tokens"] <= 128
    assert info["compressor_chunk_encoder_max_length"] == 512
    assert info["compressor_chunk_backend_calls"] == len(calls)


def test_llmlingua_compressor_recursively_splits_single_long_token_pattern(monkeypatch):
    calls = []
    tokenizer = CharTokenizer()

    class FakePromptCompressor:
        def __init__(self, model_name, device_map, use_llmlingua2, llmlingua2_config):
            self.tokenizer = tokenizer

        def compress_prompt(self, context, question="", rate=0.5, concate_question=True, **kwargs):
            chunk = context[0]
            token_count = len(tokenizer.encode(chunk, add_special_tokens=False))
            if token_count > 64:
                raise AssertionError(f"chunk too long: {token_count}")
            calls.append(token_count)
            return {
                "compressed_prompt": chunk[: max(1, len(chunk) // 2)],
                "origin_tokens": token_count,
                "compressed_tokens": max(1, token_count // 2),
            }

    monkeypatch.setattr("ccdf.compression.llmlingua.PromptCompressor", FakePromptCompressor)

    context = "x" * 257
    question = "Keep me?"

    merged_text, info = LLMLinguaCompressor(max_context_tokens_per_chunk=64).compress(
        context=context,
        question=question,
        keep_rate=0.5,
    )

    assert question in merged_text
    assert len(calls) >= 5
    assert max(calls) <= 64
    assert info["compressor_chunk_max_observed_tokens"] <= 64


def test_llmlingua_compressor_chunking_is_deterministic(monkeypatch):
    tokenizer = ExpandingTokenizer(wide_multiplier=3)

    class FakePromptCompressor:
        def __init__(self, model_name, device_map, use_llmlingua2, llmlingua2_config):
            self.tokenizer = tokenizer

        def compress_prompt(self, context, question="", rate=0.5, concate_question=True, **kwargs):
            words = context[0].split()
            compressed_words = words[::2] or words[:1]
            return {
                "compressed_prompt": " ".join(compressed_words),
                "origin_tokens": len(tokenizer.encode(context[0], add_special_tokens=False)),
                "compressed_tokens": len(tokenizer.encode(" ".join(compressed_words), add_special_tokens=False)),
            }

    monkeypatch.setattr("ccdf.compression.llmlingua.PromptCompressor", FakePromptCompressor)

    context = " ".join(f"wide{i}" for i in range(125))
    question = "Keep this question exactly."

    first_text, first_info = LLMLinguaCompressor(max_context_tokens_per_chunk=80).compress(
        context=context,
        question=question,
        keep_rate=0.5,
    )
    second_text, second_info = LLMLinguaCompressor(max_context_tokens_per_chunk=80).compress(
        context=context,
        question=question,
        keep_rate=0.5,
    )

    assert first_text == second_text
    comparable_first = {k: v for k, v in first_info.items() if k != "t_compress_ms"}
    comparable_second = {k: v for k, v in second_info.items() if k != "t_compress_ms"}
    assert comparable_first == comparable_second


def test_llmlingua_compressor_rejects_invalid_keep_rate():
    compressor = LLMLinguaCompressor()

    with pytest.raises(ValueError):
        compressor.compress(context="ctx", question="q", keep_rate=0.0)

    with pytest.raises(ValueError):
        compressor.compress(context="ctx", question="q", keep_rate=1.1)


def test_llmlingua_compressor_preserves_question_when_context_is_empty(monkeypatch):
    class FakePromptCompressor:
        def __init__(self, *args, **kwargs):
            raise AssertionError("compressor should not be initialized for empty context")

    monkeypatch.setattr("ccdf.compression.llmlingua.PromptCompressor", FakePromptCompressor)

    compressor = LLMLinguaCompressor()
    merged_text, info = compressor.compress(context="", question="Protected question?", keep_rate=0.5)

    assert merged_text == "Protected question?"
    assert info["N_original"] == 0
    assert info["N_compressed"] == 0
    assert info["R_actual"] == pytest.approx(1.0)


def test_llmlingua_compressor_accepts_explicit_model_and_device_from_config(monkeypatch):
    captured = {}
    tokenizer = ExpandingTokenizer(wide_multiplier=1)

    class FakePromptCompressor:
        def __init__(self, model_name, device_map, use_llmlingua2, llmlingua2_config):
            self.tokenizer = tokenizer
            captured["init"] = {
                "model_name": model_name,
                "device_map": device_map,
                "use_llmlingua2": use_llmlingua2,
                "llmlingua2_config": llmlingua2_config,
            }

        def compress_prompt(self, context, question="", rate=0.5, concate_question=True, **kwargs):
            return {
                "compressed_prompt": "config driven context",
                "origin_tokens": 18,
                "compressed_tokens": 9,
                "ratio": "2.0x",
            }

    monkeypatch.setattr("ccdf.compression.llmlingua.PromptCompressor", FakePromptCompressor)

    compressor = LLMLinguaCompressor.from_config(
        {
            "compression": {
                "llmlingua": {
                    "model_name": "custom/llmlingua-model",
                    "device_map": "cpu",
                    "use_llmlingua2": True,
                    "default_keep_rate": 0.33,
                }
            }
        }
    )

    merged_text, info = compressor.compress(context="alpha beta gamma", question="Protected?", keep_rate=None)

    assert captured["init"]["model_name"] == "custom/llmlingua-model"
    assert captured["init"]["device_map"] == "cpu"
    assert captured["init"]["use_llmlingua2"] is True
    assert compressor.default_keep_rate == pytest.approx(0.33)
    assert merged_text == "config driven context\n\nProtected?"
    assert info["keep_rate"] == pytest.approx(0.33)


def test_cc_llm_conditions_define_expected_keep_rates():
    assert _condition_keep_rate("Baseline-AR", 0.5) is None
    assert _condition_keep_rate("DFlash-R1", 0.5) is None
    assert _condition_keep_rate("CC-LLM-R2", 0.5) == pytest.approx(0.5)
    assert _condition_keep_rate("CC-DFlash-R2", 0.5) == pytest.approx(0.5)
    assert _condition_keep_rate("CC-LLM-R3", 0.5) == pytest.approx(0.33)
    assert _condition_keep_rate("CC-DFlash-R3", 0.5) == pytest.approx(0.33)
    assert _condition_keep_rate("LLMLingua-AR-R2", 0.5) == pytest.approx(0.5)
    assert _condition_keep_rate("LLMLingua-AR-R3", 0.5) == pytest.approx(0.33)


def test_keep_rate_percent_parser_accepts_valid_values():
    assert _parse_keep_rate_percent("67") == pytest.approx(67.0)
    assert _parse_keep_rate_percent("50") == pytest.approx(50.0)


@pytest.mark.parametrize("value", ["0", "-1", "100.1"])
def test_keep_rate_percent_parser_rejects_invalid_values(value):
    with pytest.raises(Exception, match="keep-rate-percent"):
        _parse_keep_rate_percent(value)


def test_resolve_keep_rate_uses_percent_override_for_compressed_conditions():
    keep_rate, requested_percent, requested_keep_rate = _resolve_keep_rate(
        "CC-DFlash-R2",
        default_keep_rate=0.5,
        keep_rate_percent=67.0,
    )

    assert keep_rate == pytest.approx(0.67)
    assert requested_percent == pytest.approx(67.0)
    assert requested_keep_rate == pytest.approx(0.67)


def test_resolve_keep_rate_preserves_default_when_no_override():
    keep_rate, requested_percent, requested_keep_rate = _resolve_keep_rate(
        "CC-DFlash-R2",
        default_keep_rate=0.5,
        keep_rate_percent=None,
    )

    assert keep_rate == pytest.approx(0.5)
    assert requested_percent is None
    assert requested_keep_rate is None


def test_llmlingua_ar_conditions_are_target_only():
    assert _is_ar_condition("Baseline-AR") is True
    assert _is_ar_condition("LLMLingua-AR-R2") is True
    assert _is_ar_condition("LLMLingua-AR-R3") is True
    assert _is_ar_condition("DFlash-R1") is False
    assert _is_ar_condition("CC-LLM-R2") is False


def test_prepare_cc_prompt_compresses_context_and_preserves_question():
    class FakeCompressor:
        model_name = "fake/model"

        def compress(self, context, question, keep_rate):
            assert "library" in context
            assert question == "How many books are there?"
            assert keep_rate == pytest.approx(0.5)
            return "compressed library context\n\nHow many books are there?", {
                "t_compress_ms": 12.5,
                "R_actual": 2.0,
                "N_original": 10,
                "N_compressed": 5,
                "keep_rate": keep_rate,
            }

    merged, info = _prepare_cc_prompt(
        "How many books are there?",
        FakeCompressor(),
        0.5,
        requested_keep_rate_percent=67.0,
        requested_keep_rate=0.67,
    )

    assert merged == "compressed library context\n\nHow many books are there?"
    assert info["question_preserved"] is True
    assert info["compressor_model"] == "fake/model"
    assert info["requested_keep_rate_percent"] == pytest.approx(67.0)
    assert info["requested_keep_rate"] == pytest.approx(0.67)


def test_resolve_llmlingua_config():
    from ccdf.config.loader import resolve_llmlingua_config

    old_config = {
        "compression": {
            "llmlingua": {
                "model_name": "old-large",
                "device_map": "cpu",
                "use_llmlingua2": True,
                "default_keep_rate": 0.5,
            }
        }
    }
    cfg = resolve_llmlingua_config(old_config, profile="large")
    assert cfg["model_name"] == "old-large"

    new_config = {
        "compression": {
            "large_llmlingua": {
                "model_name": "microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
                "device_map": "cpu",
                "use_llmlingua2": True,
                "default_keep_rate": 0.5,
            },
            "light_llmlingua": {
                "model_name": "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
                "device_map": "cuda:0",
                "use_llmlingua2": True,
                "default_keep_rate": 0.5,
            }
        }
    }
    cfg = resolve_llmlingua_config(new_config, profile="large")
    assert cfg["model_name"] == "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"

    cfg = resolve_llmlingua_config(new_config, profile="light")
    assert cfg["model_name"] == "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank"

    cfg = resolve_llmlingua_config(new_config)
    assert cfg["model_name"] == "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"

    with pytest.raises(ValueError, match="Requested compressor profile 'light' but compression.light_llmlingua is not configured."):
        resolve_llmlingua_config(old_config, profile="light")

    cfg = resolve_llmlingua_config(new_config, profile="large_llmlingua")
    assert cfg["model_name"] == "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"

    cfg = resolve_llmlingua_config(new_config, profile="light_llmlingua")
    assert cfg["model_name"] == "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank"


def test_llmlingua_compressor_from_config_profile():
    new_config = {
        "compression": {
            "large_llmlingua": {
                "model_name": "large-model",
                "device_map": "cpu",
            },
            "light_llmlingua": {
                "model_name": "light-model",
                "device_map": "cpu",
            }
        }
    }
    comp_large = LLMLinguaCompressor.from_config(new_config, profile="large")
    assert comp_large.model_name == "large-model"

    comp_light = LLMLinguaCompressor.from_config(new_config, profile="light")
    assert comp_light.model_name == "light-model"

