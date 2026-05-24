from htfsd.tokenization.prompt_adapter import format_prompt


def test_gemma_prompt_adapter_does_not_prepend_bos():
    prompt = format_prompt("gemma", "Write a five word greeting.")

    assert prompt == "<|turn>user\nWrite a five word greeting.<turn|>\n<|turn>model\n"
    assert not prompt.startswith("<bos>")


def test_qwen_prompt_adapter_uses_qwen_chat_shape_without_bos():
    prompt = format_prompt("qwen", "Write one sentence.")

    assert prompt == "<|im_start|>user\nWrite one sentence.<|im_end|>\n<|im_start|>assistant\n"
    assert not prompt.startswith("<bos>")


def test_raw_prompt_adapter_returns_prompt_unchanged():
    assert format_prompt("raw", "Plain prompt") == "Plain prompt"
