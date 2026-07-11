"""Production NF4 DFlash with structural target verification."""

from __future__ import annotations

import time

import torch

from ccdf.dflash.utils import extract_context_feature, sample
from ccdf.dflash.verifier import TargetBlockVerifierState
from ccdf.inference.generation_common import synchronize_if_cuda
from ccdf.inference.output_contract import OutputContractState
from ccdf.inference.schemas import GenerationConfig, GenerationResult


@torch.inference_mode()
def generate_dflash(target, drafter, tokenizer, input_ids: torch.Tensor, config: GenerationConfig) -> GenerationResult:
    """Generate with one target verification forward per proposed block.

    Exact equality with cached Baseline-AR is deliberately not a pass gate for
    the locked NF4 target. Every accepted/correction token is nevertheless
    audited against the target logits from its block-verification execution.
    """

    if config.dflash_mode != "normal":
        raise ValueError("production DFlash supports only dflash_mode='normal'")
    drafter.eval()
    target.eval()
    request_start = time.perf_counter()
    block_size = int(config.dflash_block_size or drafter.block_size)
    if block_size < 2:
        raise ValueError("production DFlash block_size must be at least 2")

    verifier = TargetBlockVerifierState(
        target,
        input_ids,
        config.temperature,
        list(drafter.target_layer_ids),
    )
    controller = OutputContractState(
        tokenizer=tokenizer,
        dataset=config.dataset,
        stop_token_ids=config.stop_token_ids,
        max_new_tokens=config.max_new_tokens,
        policy_text=config.prompt_policy_text,
        settings=config.output_contract_settings,
    )

    synchronize_if_cuda(target.device)
    prefill_start = time.perf_counter()
    seed, target_hidden = verifier.prefill()
    synchronize_if_cuda(target.device)
    target_prefill_ms = (time.perf_counter() - prefill_start) * 1000

    generated = [int(seed)]
    target_seed_tokens = 1
    decision = controller.observe(generated)
    from transformers import DynamicCache

    past_key_values_draft = DynamicCache()
    raw_acceptance_lengths: list[int] = []
    emitted_acceptance_lengths: list[int] = []
    structural_audit: list[dict[str, object]] = []
    draft_tokens_proposed = 0
    accepted_draft_tokens = 0
    correction_tokens = 0
    bonus_target_tokens = 0
    draft_forward_calls = 0

    synchronize_if_cuda(target.device)
    decode_start = time.perf_counter()
    while not decision.should_stop and len(generated) < config.max_new_tokens:
        start = verifier.prompt_length + len(generated) - 1
        remaining = config.max_new_tokens - len(generated)
        proposal_slots = min(block_size - 1, remaining)
        if proposal_slots <= 0:
            break

        block_ids = torch.full(
            (1, block_size),
            int(drafter.mask_token_id),
            dtype=torch.long,
            device=target.device,
        )
        block_ids[:, 0] = generated[-1]
        draft_positions = torch.arange(
            past_key_values_draft.get_seq_length(),
            start + block_size,
            device=target.device,
        ).unsqueeze(0)
        noise_embedding = target.model.embed_tokens(block_ids)
        draft_hidden = drafter(
            target_hidden=target_hidden,
            noise_embedding=noise_embedding,
            position_ids=draft_positions,
            past_key_values=past_key_values_draft,
            use_cache=True,
            is_causal=False,
        )
        draft_forward_calls += 1
        draft_logits = target.lm_head(draft_hidden[:, -block_size + 1 :, :])
        past_key_values_draft.crop(start)
        proposed = sample(draft_logits, config.temperature)[0, :proposal_slots]
        block_ids[:, 1 : 1 + proposal_slots] = proposed
        draft_tokens_proposed += proposal_slots

        verification = verifier.verify(
            block_ids=block_ids,
            start=start,
            proposal_count=proposal_slots,
        )
        raw_acceptance_lengths.append(verification.raw_advance)

        emitted_this_block: list[int] = []
        emitted_accepted = 0
        emitted_correction = 0
        emitted_bonus = 0
        for index, token in enumerate(verification.raw_emitted_tokens):
            if len(generated) >= config.max_new_tokens:
                break
            generated.append(int(token))
            emitted_this_block.append(int(token))
            if index < verification.accepted_count:
                emitted_accepted += 1
            elif verification.all_proposals_accepted:
                emitted_bonus += 1
            else:
                emitted_correction += 1
            decision = controller.observe(generated)
            if decision.should_stop:
                break

        emitted_advance = len(emitted_this_block)
        if emitted_advance <= 0:
            raise RuntimeError("target verification emitted no token")
        emitted_acceptance_lengths.append(emitted_advance)
        accepted_draft_tokens += emitted_accepted
        correction_tokens += emitted_correction
        bonus_target_tokens += emitted_bonus

        boundary_clipped = emitted_advance != verification.raw_advance
        if boundary_clipped:
            cache_after = verifier.crop_after_boundary(
                start=start,
                accepted_count=verification.accepted_count,
                emitted_from_block=emitted_advance,
            )
        else:
            cache_after = verifier.cache_length

        accepted_match = (
            verification.proposals[: verification.accepted_count]
            == verification.verifier_argmax_ids[: verification.accepted_count]
        )
        correction_index_valid = (
            verification.correction_token_id
            == sample(verification.target_output.logits, config.temperature)[0, verification.accepted_count].item()
        )
        expected_cache = (
            start + verification.raw_advance
            if not boundary_clipped
            else start + 1 + min(emitted_advance, verification.accepted_count)
        )
        audit = {
            "block_index": len(structural_audit),
            "start": start,
            "proposal_token_ids": verification.proposals,
            "verifier_argmax_ids": verification.verifier_argmax_ids,
            "accepted_prefix_length": verification.accepted_count,
            "first_mismatch_index": verification.first_mismatch_index,
            "correction_token_id": verification.correction_token_id,
            "all_proposals_accepted": verification.all_proposals_accepted,
            "raw_emitted_token_ids": verification.raw_emitted_tokens,
            "emitted_token_ids": emitted_this_block,
            "cache_length_before": verification.cache_length_before,
            "cache_length_after": cache_after,
            "expected_cache_length_after": expected_cache,
            "cache_positions": verification.cache_positions,
            "boundary_clipped": boundary_clipped,
            "stop_reason": decision.stop_reason,
            "accepted_tokens_match_target": accepted_match,
            "correction_index_valid": bool(correction_index_valid),
            "cache_progression_valid": cache_after == expected_cache,
            "structural_pass": bool(
                accepted_match and correction_index_valid and cache_after == expected_cache
            ),
        }
        structural_audit.append(audit)
        if not audit["structural_pass"]:
            raise RuntimeError(f"DFlash structural verification failed: {audit}")
        if decision.should_stop:
            break

        # The verifier output already contains hidden states for the committed
        # seed + accepted proposal prefix; no extra target hidden refresh call.
        target_hidden = verification.target_hidden

    synchronize_if_cuda(target.device)
    decode_total_ms = (time.perf_counter() - decode_start) * 1000
    generation_e2e_ms = (time.perf_counter() - request_start) * 1000
    if not decision.should_stop and len(generated) >= config.max_new_tokens:
        decision = controller.observe(generated)

    rollback_tokens = draft_tokens_proposed - accepted_draft_tokens
    if len(generated) != target_seed_tokens + sum(emitted_acceptance_lengths):
        raise RuntimeError("seed-aware emitted token accounting failed")
    if verifier.target_block_verification_calls != len(emitted_acceptance_lengths):
        raise RuntimeError("verification call accounting failed")

    output_ids = input_ids[0].detach().cpu().tolist() + generated
    result = GenerationResult(
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
        target_seed_tokens=target_seed_tokens,
        raw_acceptance_lengths=raw_acceptance_lengths,
        emitted_acceptance_lengths=emitted_acceptance_lengths,
        acceptance_lengths=list(emitted_acceptance_lengths),
        verification_calls=verifier.target_block_verification_calls,
        target_prefill_calls=verifier.target_prefill_calls,
        target_block_verification_calls=verifier.target_block_verification_calls,
        target_single_token_fallback_calls=verifier.target_single_token_fallback_calls,
        target_hidden_refresh_calls=verifier.target_hidden_refresh_calls,
        total_target_forward_calls=verifier.total_target_forward_calls,
        draft_forward_calls=draft_forward_calls,
        draft_tokens_proposed=draft_tokens_proposed,
        accepted_draft_tokens=accepted_draft_tokens,
        correction_tokens=correction_tokens,
        bonus_target_tokens=bonus_target_tokens,
        rollback_tokens=rollback_tokens,
        structural_audit=structural_audit,
        cache_audit=structural_audit,
        target_prefill_ms=target_prefill_ms,
        decode_total_ms=decode_total_ms,
        generation_request_e2e_ms=generation_e2e_ms,
        warm_request_e2e_ms=generation_e2e_ms,
        request_e2e_ms=generation_e2e_ms,
    )
    return result
