"""Minimal prompt formatting fallbacks for GGUF smoke tests."""

from __future__ import annotations


def format_prompt(model_family: str, prompt: str) -> str:
    """Format a prompt for a model family without adding duplicate BOS tokens."""

    family = model_family.lower()
    if family == "gemma":
        return f"<|turn>user\n{prompt}<turn|>\n<|turn>model\n"
    if family == "qwen":
        return f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
    if family == "raw":
        return prompt
    raise ValueError(f"unknown model family: {model_family}")
