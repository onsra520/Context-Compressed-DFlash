from __future__ import annotations

import pytest

from ccdf.compression import PassthroughCompressor, merge, segment_gsm8k
from ccdf.compression.llmlingua import LLMLinguaCompressor


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

    class FakePromptCompressor:
        def __init__(self, model_name, device_map, use_llmlingua2, llmlingua2_config):
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

    class FakePromptCompressor:
        def __init__(self, model_name, device_map, use_llmlingua2, llmlingua2_config):
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
