"""Common generation helpers."""

from __future__ import annotations

from ccdf.inference.schemas import GenerationConfig


def tokenize_prompt(tokenizer, prompt: str, device):
    return tokenizer(prompt, return_tensors="pt").input_ids.to(device)


def decode_new_text(tokenizer, output_ids, prompt_token_count: int) -> str:
    return tokenizer.decode(output_ids[0][prompt_token_count:], skip_special_tokens=True)


def stop_reason(output_ids: list[int], config: GenerationConfig) -> str:
    return "eos" if any(token in config.stop_token_ids for token in output_ids) else "max_new_tokens"
