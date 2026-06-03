from __future__ import annotations

from ccdf.compression import PassthroughCompressor, merge, segment_gsm8k


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