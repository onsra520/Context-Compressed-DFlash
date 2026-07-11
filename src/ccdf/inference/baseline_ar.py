"""Production cached autoregressive generation."""

from __future__ import annotations

import time

import torch

from ccdf.inference.cached_target import CachedAutoregressiveState
from ccdf.inference.generation_common import synchronize_if_cuda
from ccdf.inference.output_contract import OutputContractState
from ccdf.inference.schemas import GenerationConfig, GenerationResult


@torch.inference_mode()
def generate_baseline(model, tokenizer, input_ids: torch.Tensor, config: GenerationConfig) -> GenerationResult:
    request_start = time.perf_counter()
    state = CachedAutoregressiveState(model, input_ids, config.temperature)
    controller = OutputContractState(
        tokenizer=tokenizer,
        dataset=config.dataset,
        stop_token_ids=config.stop_token_ids,
        max_new_tokens=config.max_new_tokens,
        policy_text=config.prompt_policy_text,
        settings=config.output_contract_settings,
    )

    synchronize_if_cuda(model.device)
    prefill_start = time.perf_counter()
    next_token = state.prefill()
    synchronize_if_cuda(model.device)
    target_prefill_ms = (time.perf_counter() - prefill_start) * 1000

    generated: list[int] = []
    decision = None
    synchronize_if_cuda(model.device)
    decode_start = time.perf_counter()
    while len(generated) < config.max_new_tokens:
        generated.append(int(next_token))
        state.commit(int(next_token))
        decision = controller.observe(generated)
        if decision.should_stop:
            break
        next_token = state.next_token(generated[-1])
    synchronize_if_cuda(model.device)
    decode_total_ms = (time.perf_counter() - decode_start) * 1000
    generation_e2e_ms = (time.perf_counter() - request_start) * 1000
    if decision is None:
        decision = controller.observe(generated)

    output_ids = input_ids[0].detach().cpu().tolist() + generated
    return GenerationResult(
        generated_text=decision.raw_generated_text,
        raw_generated_text=decision.raw_generated_text,
        validated_answer=decision.validated_answer,
        output_token_ids=output_ids,
        generated_token_ids=generated,
        prompt_token_count=int(input_ids.shape[1]),
        output_token_count=len(generated),
        stop_reason=decision.stop_reason or "max_new_tokens",
        eos_hit=decision.eos_hit,
        output_contract_hit=decision.output_contract_hit,
        cap_hit=decision.cap_hit,
        repetition_detected=decision.health.repetition_detected,
        instruction_echo_detected=decision.health.instruction_echo_detected,
        degeneration_reason=(decision.stop_reason if decision.stop_reason in {"repetition", "instruction_echo"} else None),
        output_health=decision.to_dict()["health"],
        target_prefill_calls=1,
        total_target_forward_calls=state.target_forward_calls,
        target_prefill_ms=target_prefill_ms,
        decode_total_ms=decode_total_ms,
        generation_request_e2e_ms=generation_e2e_ms,
        warm_request_e2e_ms=generation_e2e_ms,
        request_e2e_ms=generation_e2e_ms,
    )
