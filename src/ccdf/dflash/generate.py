"""Instrumented DFlash generation."""

from __future__ import annotations

import torch
from transformers import DynamicCache

from ccdf.dflash.utils import extract_context_feature, sample
from ccdf.inference.generation_common import decode_new_text, stop_reason, tokenize_prompt
from ccdf.inference.schemas import GenerationConfig, GenerationResult


@torch.inference_mode()
def generate_dflash(target, drafter, tokenizer, prompt: str, config: GenerationConfig) -> GenerationResult:
    drafter.eval()
    target.eval()
    input_ids = tokenize_prompt(tokenizer, prompt, target.device)
    num_input_tokens = input_ids.shape[1]
    max_length = num_input_tokens + config.max_new_tokens
    block_size = drafter.block_size
    output_ids = torch.full(
        (1, max_length + block_size),
        drafter.mask_token_id,
        dtype=torch.long,
        device=target.device,
    )
    position_ids = torch.arange(output_ids.shape[1], device=target.device).unsqueeze(0)
    past_key_values_target = DynamicCache()
    past_key_values_draft = DynamicCache()

    output = target(
        input_ids,
        position_ids=position_ids[:, :num_input_tokens],
        past_key_values=past_key_values_target,
        use_cache=True,
        logits_to_keep=1,
        output_hidden_states=True,
    )
    output_ids[:, :num_input_tokens] = input_ids
    output_ids[:, num_input_tokens : num_input_tokens + 1] = sample(output.logits, config.temperature)
    target_hidden = extract_context_feature(output.hidden_states, drafter.target_layer_ids)

    acceptance_lengths: list[int] = []
    draft_tokens_proposed = 0
    start = num_input_tokens
    while start < max_length:
        block_output_ids = output_ids[:, start : start + block_size].clone()
        block_position_ids = position_ids[:, start : start + block_size]
        noise_embedding = target.model.embed_tokens(block_output_ids)
        draft_logits = target.lm_head(
            drafter(
                target_hidden=target_hidden,
                noise_embedding=noise_embedding,
                position_ids=position_ids[:, past_key_values_draft.get_seq_length() : start + block_size],
                past_key_values=past_key_values_draft,
                use_cache=True,
                is_causal=False,
            )[:, -block_size + 1 :, :]
        )
        past_key_values_draft.crop(start)
        proposed = sample(draft_logits, config.temperature)
        block_output_ids[:, 1:] = proposed
        draft_tokens_proposed += proposed.shape[1]

        output = target(
            block_output_ids,
            position_ids=block_position_ids,
            past_key_values=past_key_values_target,
            use_cache=True,
            output_hidden_states=True,
        )
        posterior = sample(output.logits, config.temperature)
        acceptance_length = (block_output_ids[:, 1:] == posterior[:, :-1]).cumprod(dim=1).sum(dim=1)[0].item()
        output_ids[:, start : start + acceptance_length + 1] = block_output_ids[
            :, : acceptance_length + 1
        ]
        output_ids[:, start + acceptance_length + 1] = posterior[:, acceptance_length]
        start += acceptance_length + 1
        past_key_values_target.crop(start)
        target_hidden = extract_context_feature(output.hidden_states, drafter.target_layer_ids)[
            :, : acceptance_length + 1, :
        ]
        acceptance_lengths.append(acceptance_length + 1)
        generated_slice = output_ids[0, num_input_tokens:start]
        if any(stop_id in generated_slice for stop_id in config.stop_token_ids):
            break

    output_ids = output_ids[:, :max_length]
    output_ids = output_ids[:, output_ids[0] != drafter.mask_token_id]
    if config.stop_token_ids:
        stop_tensor = torch.tensor(config.stop_token_ids, device=output_ids.device)
        stop_indices = torch.isin(output_ids[0][num_input_tokens:], stop_tensor).nonzero(as_tuple=True)[0]
        if stop_indices.numel() > 0:
            output_ids = output_ids[:, : num_input_tokens + stop_indices[0] + 1]

    ids = output_ids[0].detach().cpu().tolist()
    return GenerationResult(
        generated_text=decode_new_text(tokenizer, output_ids, num_input_tokens),
        output_token_ids=ids,
        prompt_token_count=num_input_tokens,
        output_token_count=len(ids) - num_input_tokens,
        stop_reason=stop_reason(ids[num_input_tokens:], config),
        acceptance_lengths=acceptance_lengths,
        verification_calls=len(acceptance_lengths),
        draft_tokens_proposed=draft_tokens_proposed,
    )
