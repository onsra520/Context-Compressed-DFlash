from __future__ import annotations

from ccdf.compression import PassthroughCompressor
from ccdf.pipeline import CCDFlashPipeline, build_prompt


class DummyTokenizer:
    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True, enable_thinking=False):
        return f"thinking={enable_thinking};messages={len(messages)}"


def test_prompt_builder_uses_tokenizer_template():
    prompt = build_prompt([{"role": "user", "content": "hello"}], DummyTokenizer(), False)
    assert prompt == "thinking=False;messages=1"


def test_pipeline_description_mentions_components():
    pipeline = CCDFlashPipeline(PassthroughCompressor(), object())
    description = pipeline.describe()
    assert description["compression"] == "PassthroughCompressor"