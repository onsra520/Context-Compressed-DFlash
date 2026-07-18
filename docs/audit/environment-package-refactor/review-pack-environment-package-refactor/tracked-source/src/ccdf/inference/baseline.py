"""Cached autoregressive baseline using the configured AWQ model."""

from __future__ import annotations

import time
from typing import Any

import torch
from transformers import DynamicCache

from ..runtime.device import collect_memory, current_memory_state, reset_peak_memory, synchronize
from ..schemas import GenerationOutput, GenerationSettings, TimingBreakdown
from .sampling import sample
from .stopping import BlockStopController


@torch.inference_mode()
def generate_baseline(
    model: Any,
    tokenizer: Any,
    input_ids: torch.Tensor,
    settings: GenerationSettings,
    *,
    model_metadata: dict[str, Any],
) -> GenerationOutput:
    reset_peak_memory()
    memory_before = current_memory_state()
    request_start = time.perf_counter()
    cache = DynamicCache()
    controller = BlockStopController(
        tokenizer=tokenizer,
        stop_token_ids=settings.stop_token_ids,
        max_new_tokens=settings.max_new_tokens,
        dataset=settings.dataset,
    )

    synchronize(model.device)
    prefill_start = time.perf_counter()
    positions = torch.arange(input_ids.shape[1], device=input_ids.device).unsqueeze(0)
    output = model(
        input_ids,
        position_ids=positions,
        attention_mask=torch.ones_like(input_ids),
        past_key_values=cache,
        use_cache=True,
        logits_to_keep=1,
        output_hidden_states=False,
    )
    next_token = int(sample(output.logits, settings.temperature)[0, -1].item())
    synchronize(model.device)
    target_prefill_ms = (time.perf_counter() - prefill_start) * 1000.0

    generated: list[int] = []
    stop_reason: str | None = None
    synchronize(model.device)
    decode_start = time.perf_counter()
    while len(generated) < settings.max_new_tokens:
        generated.append(next_token)
        stop_reason = controller.token_reason(next_token, len(generated))
        if stop_reason:
            break
        if settings.output_contract_mode == "block_boundary":
            boundary = controller.block_boundary(generated)
            if boundary.should_stop:
                stop_reason = boundary.reason
                break
        position = int(input_ids.shape[1] + len(generated) - 1)
        token = torch.tensor([[next_token]], device=input_ids.device, dtype=torch.long)
        attention_mask = torch.ones((1, position + 1), device=input_ids.device, dtype=torch.long)
        output = model(
            token,
            position_ids=torch.tensor([[position]], device=input_ids.device),
            attention_mask=attention_mask,
            past_key_values=cache,
            use_cache=True,
            logits_to_keep=1,
            output_hidden_states=False,
        )
        next_token = int(sample(output.logits, settings.temperature)[0, -1].item())
    synchronize(model.device)
    decode_total_ms = (time.perf_counter() - decode_start) * 1000.0
    generation_total_ms = (time.perf_counter() - request_start) * 1000.0
    stop, health = controller.finalize(generated, stop_reason)
    memory = collect_memory(limit_gib=None)
    memory.allocated_before_bytes = memory_before["allocated_bytes"]
    memory.reserved_before_bytes = memory_before["reserved_bytes"]
    return GenerationOutput(
        condition="baseline",
        text=stop.text,
        prompt_tokens=int(input_ids.shape[1]),
        output_tokens=len(generated),
        generated_token_ids=generated,
        stop_reason=stop.reason or "completed",
        timing=TimingBreakdown(
            target_prefill_ms=target_prefill_ms,
            decode_total_ms=decode_total_ms,
            generation_total_ms=generation_total_ms,
            warm_request_ms=generation_total_ms,
        ),
        memory=memory,
        dflash=None,
        model=model_metadata,
        runtime={"output_health": health},
    )
