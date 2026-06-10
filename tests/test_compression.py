from __future__ import annotations

import pytest

from ccdf.compression import PassthroughCompressor, merge, segment_gsm8k
from ccdf.compression.llmlingua import LLMLinguaCompressor
from scripts.run_mvp import _condition_keep_rate, _is_ar_condition, _prepare_cc_prompt


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

    merged, info = _prepare_cc_prompt("How many books are there?", FakeCompressor(), 0.5)

    assert merged == "compressed library context\n\nHow many books are there?"
    assert info["question_preserved"] is True
    assert info["compressor_model"] == "fake/model"
