"""Instrumented DFlash generation with canonical target verification."""

from __future__ import annotations

import time

import torch
from transformers import DynamicCache

from ccdf.dflash.utils import extract_context_feature, sample
from ccdf.inference.generation_common import decode_new_text, stop_reason, synchronize_if_cuda, tokenize_prompt
from ccdf.inference.schemas import GenerationConfig, GenerationResult
from ccdf.inference.target_execution import TargetExecutionState


@torch.inference_mode()
def generate_dflash(target, drafter, tokenizer, prompt: str, config: GenerationConfig) -> GenerationResult:
    """Generate with DFlash proposals and oracle-equivalent target commits.

    The drafter remains block based.  Each proposed token is committed only
    after the same full-prefix target call used by Baseline selects it.  This
    is intentionally correctness-first for the locked NF4 target.
    """
    if config.dflash_mode not in {"normal", "reject_all", "oracle_draft"}:
        raise ValueError(f"unsupported DFlash diagnostic mode: {config.dflash_mode}")
    drafter.eval()
    target.eval()
    input_ids = tokenize_prompt(tokenizer, prompt, target.device)
    request_start = time.perf_counter()
    state = TargetExecutionState(target, input_ids, config.temperature)
    prompt_tokens = state.prompt_length
    block_size = config.dflash_block_size or drafter.block_size
    if block_size < 1:
        raise ValueError("dflash_block_size must be positive")

    synchronize_if_cuda(target.device)
    prefill_start = time.perf_counter()
    seed = state.next_token(output_hidden_states=config.dflash_mode == "normal")
    target_hidden = (
        extract_context_feature(state.last_output.hidden_states, drafter.target_layer_ids)
        if config.dflash_mode == "normal"
        else None
    )
    state.commit(seed)
    synchronize_if_cuda(target.device)
    target_prefill_ms = (time.perf_counter() - prefill_start) * 1000

    generated = [seed]
    past_key_values_draft = DynamicCache()
    acceptance_lengths: list[int] = []
    draft_tokens_proposed = 0
    cache_audit: list[dict[str, object]] = []
    synchronize_if_cuda(target.device)
    decode_start = time.perf_counter()
    while len(generated) < config.max_new_tokens and generated[-1] not in config.stop_token_ids:
        start = prompt_tokens + len(generated) - 1
        proposal_slots = min(block_size - 1, config.max_new_tokens - len(generated))
        if proposal_slots < 0:
            break
        # A size-one block has no draft slot but must still execute one
        # canonical target correction; it is the target-greedy control mode.
        if proposal_slots == 0:
            correction = state.next_token()
            state.commit(correction)
            generated.append(correction)
            acceptance_lengths.append(1)
            cache_audit.append(
                {"start": start, "proposal_count": 0, "accepted": 0, "corrected": True, "target": state.diagnostic_state()}
            )
            continue
        if config.dflash_mode == "normal":
            block_ids = torch.full(
                (1, block_size), drafter.mask_token_id, dtype=torch.long, device=target.device
            )
            block_ids[:, 0] = generated[-1]
            # The draft attention keys comprise its cached prefix plus the target
            # hidden segment and current noise block.  Qwen rotary positions must
            # cover that complete key sequence, as in the pinned upstream code.
            draft_positions = torch.arange(
                past_key_values_draft.get_seq_length(), start + block_size, device=target.device
            ).unsqueeze(0)
            noise_embedding = target.model.embed_tokens(block_ids)
            draft_logits = target.lm_head(
                drafter(
                    target_hidden=target_hidden,
                    noise_embedding=noise_embedding,
                    position_ids=draft_positions,
                    past_key_values=past_key_values_draft,
                    use_cache=True,
                    is_causal=False,
                )[:, -block_size + 1 :, :]
            )
            past_key_values_draft.crop(start)
            proposed = sample(draft_logits, config.temperature)[0, :proposal_slots].tolist()
        else:
            # These controls isolate verifier/commit behavior from drafter
            # quality and therefore deliberately avoid drafter execution.
            proposed = [0] * proposal_slots
        draft_tokens_proposed += len(proposed)

        accepted = 0
        corrected = False
        for proposal in proposed:
            canonical = state.next_token()
            candidate = canonical if config.dflash_mode == "oracle_draft" else int(proposal)
            if config.dflash_mode == "reject_all" or candidate != canonical:
                state.commit(canonical)
                generated.append(canonical)
                corrected = True
                break
            state.commit(candidate)
            generated.append(candidate)
            accepted += 1
            if candidate in config.stop_token_ids or len(generated) >= config.max_new_tokens:
                break
        advanced = accepted + int(corrected)
        if advanced:
            acceptance_lengths.append(advanced)
        cache_audit.append(
            {
                "start": start,
                "proposal_count": len(proposed),
                "accepted": accepted,
                "corrected": corrected,
                "target": state.diagnostic_state(),
            }
        )
        if generated[-1] in config.stop_token_ids or len(generated) >= config.max_new_tokens:
            break
        # Prime the drafter with exactly the committed target segment.  This
        # mirrors the old cache boundary but derives hidden states from the
        # canonical target execution rather than an independent target cache.
        if config.dflash_mode == "normal":
            state.forward(output_hidden_states=True)
            target_hidden = extract_context_feature(state.last_output.hidden_states, drafter.target_layer_ids)[
                :, -advanced:, :
            ]
    synchronize_if_cuda(target.device)
    decode_total_ms = (time.perf_counter() - decode_start) * 1000
    output_ids = torch.cat(
        [input_ids, torch.tensor([generated], device=target.device, dtype=torch.long)], dim=1
    )
    ids = output_ids[0].detach().cpu().tolist()
    request_e2e_ms = (time.perf_counter() - request_start) * 1000
    result = GenerationResult(
        generated_text=decode_new_text(tokenizer, output_ids, prompt_tokens),
        output_token_ids=ids,
        prompt_token_count=prompt_tokens,
        output_token_count=len(generated),
        stop_reason=stop_reason(generated, config),
        acceptance_lengths=acceptance_lengths,
        verification_calls=len(acceptance_lengths),
        draft_tokens_proposed=draft_tokens_proposed,
        target_prefill_ms=target_prefill_ms,
        decode_total_ms=decode_total_ms,
        request_e2e_ms=request_e2e_ms,
    )
    result.cache_audit = cache_audit
    return result
