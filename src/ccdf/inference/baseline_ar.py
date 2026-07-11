"""Baseline autoregressive generation."""

from __future__ import annotations

import time

import torch

from ccdf.inference.generation_common import decode_new_text, stop_reason, synchronize_if_cuda, tokenize_prompt
from ccdf.inference.schemas import GenerationConfig, GenerationResult
from ccdf.inference.target_execution import TargetExecutionState


@torch.inference_mode()
def generate_baseline(model, tokenizer, prompt: str, config: GenerationConfig) -> GenerationResult:
    input_ids = tokenize_prompt(tokenizer, prompt, model.device)
    request_start = time.perf_counter()
    synchronize_if_cuda(model.device)
    prefill_start = time.perf_counter()
    state = TargetExecutionState(model, input_ids, config.temperature)
    next_token = state.next_token()
    synchronize_if_cuda(model.device)
    target_prefill_ms = (time.perf_counter() - prefill_start) * 1000

    generated = [next_token]
    state.commit(next_token)
    synchronize_if_cuda(model.device)
    decode_start = time.perf_counter()
    while len(generated) < config.max_new_tokens:
        if generated[-1] in config.stop_token_ids:
            break
        next_token = state.next_token()
        generated.append(next_token)
        state.commit(next_token)
    generated_ids = torch.tensor([generated], device=model.device, dtype=torch.long)
    output_ids = torch.cat([input_ids, generated_ids], dim=1)
    synchronize_if_cuda(model.device)
    decode_total_ms = (time.perf_counter() - decode_start) * 1000
    request_e2e_ms = (time.perf_counter() - request_start) * 1000

    ids = output_ids[0].detach().cpu().tolist()
    prompt_tokens = input_ids.shape[1]
    return GenerationResult(
        generated_text=decode_new_text(tokenizer, output_ids, prompt_tokens),
        output_token_ids=ids,
        prompt_token_count=prompt_tokens,
        output_token_count=len(ids) - prompt_tokens,
        stop_reason=stop_reason(ids[prompt_tokens:], config),
        target_prefill_ms=target_prefill_ms,
        decode_total_ms=decode_total_ms,
        request_e2e_ms=request_e2e_ms,
    )
