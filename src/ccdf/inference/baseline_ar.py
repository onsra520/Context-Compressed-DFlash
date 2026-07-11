"""Baseline autoregressive generation."""

from __future__ import annotations

import torch

from ccdf.inference.generation_common import decode_new_text, stop_reason, tokenize_prompt
from ccdf.inference.schemas import GenerationConfig, GenerationResult


@torch.inference_mode()
def generate_baseline(model, tokenizer, prompt: str, config: GenerationConfig) -> GenerationResult:
    input_ids = tokenize_prompt(tokenizer, prompt, model.device)
    output_ids = model.generate(
        input_ids=input_ids,
        max_new_tokens=config.max_new_tokens,
        do_sample=config.temperature > 0,
        temperature=None if config.temperature == 0 else config.temperature,
        pad_token_id=tokenizer.eos_token_id,
        eos_token_id=list(config.stop_token_ids),
    )
    ids = output_ids[0].detach().cpu().tolist()
    prompt_tokens = input_ids.shape[1]
    return GenerationResult(
        generated_text=decode_new_text(tokenizer, output_ids, prompt_tokens),
        output_token_ids=ids,
        prompt_token_count=prompt_tokens,
        output_token_count=len(ids) - prompt_tokens,
        stop_reason=stop_reason(ids[prompt_tokens:], config),
    )
