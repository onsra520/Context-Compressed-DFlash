"""Optimized standalone D-Flash generation loop."""

from __future__ import annotations

import time
from typing import Any, Callable

import torch
from transformers import DynamicCache

from ..infrastructure.device import EventSpan, collect_memory, current_memory_state, enforce_memory_gate, reset_peak_memory, synchronize
from ..inference.sampling import sample
from ..inference.stopping import BlockStopController
from ..runtime.schemas import DFlashStats, GenerationOutput, GenerationSettings, TimingBreakdown
from .policy import BlockPolicy
from .verifier import TargetVerifier


@torch.inference_mode()
def generate_dflash(
    target: Any,
    drafter: Any,
    tokenizer: Any,
    input_ids: torch.Tensor,
    settings: GenerationSettings,
    *,
    model_metadata: dict[str, Any],
    block_policy: BlockPolicy,
    memory_limit_gib: float,
    full_structural_audit: bool = False,
    compact_structural_audit: bool = True,
    profile_components: bool = False,
    gpu_resident_acceptance: bool = True,
    allow_subblock_shapes: bool = True,
    on_tokens_committed: Callable[[list[int], str], None] | None = None,
) -> GenerationOutput:
    target.eval()
    drafter.eval()
    reset_peak_memory()
    memory_before = current_memory_state()
    request_start = time.perf_counter()
    controller = BlockStopController(
        tokenizer=tokenizer,
        stop_token_ids=settings.stop_token_ids,
        max_new_tokens=settings.max_new_tokens,
        dataset=settings.dataset,
    )
    verifier = TargetVerifier(
        target,
        input_ids,
        settings.temperature,
        list(drafter.target_layer_ids),
        gpu_resident_acceptance=gpu_resident_acceptance,
    )
    drafter_dtype = next(drafter.parameters()).dtype
    target_head_parameter = next(target.lm_head.parameters(), None)
    target_head_dtype = (
        target_head_parameter.dtype if target_head_parameter is not None else drafter_dtype
    )

    synchronize(target.device)
    prefill_start = time.perf_counter()
    seed, target_hidden = verifier.prefill()
    synchronize(target.device)
    target_prefill_ms = (time.perf_counter() - prefill_start) * 1000.0

    generated = [int(seed)]
    streamed_text = ""
    if on_tokens_committed is not None:
        streamed_text = tokenizer.decode(
            generated,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )
        on_tokens_committed([int(seed)], streamed_text)
    stop_reason = controller.token_reason(seed, len(generated))
    draft_cache = DynamicCache()
    stats = DFlashStats(target_prefill_calls=1)
    first_draft_span = EventSpan(enabled=profile_components)
    reference_decode_span = EventSpan(enabled=profile_components)
    reference_decode_started = False
    first_draft_recorded = False
    first_block_advance = 0
    pending_block_profiles: list[tuple[dict[str, float | int], EventSpan, EventSpan]] = []

    synchronize(target.device)
    decode_start = time.perf_counter()
    while stop_reason is None and len(generated) < settings.max_new_tokens:
        requested_block = int(block_policy.next_block_size())
        checkpoint_block = int(drafter.block_size)
        if not allow_subblock_shapes and requested_block != checkpoint_block:
            requested_block = checkpoint_block
        remaining = settings.max_new_tokens - len(generated)
        proposal_count = (
            min(requested_block - 1, remaining)
            if allow_subblock_shapes
            else requested_block - 1
        )
        if proposal_count <= 0:
            break
        physical_block_size = proposal_count + 1
        start = verifier.prompt_length + len(generated) - 1
        block_ids = torch.full(
            (1, physical_block_size),
            int(drafter.mask_token_id),
            dtype=torch.long,
            device=target.device,
        )
        block_ids[:, 0] = generated[-1]
        positions = torch.arange(
            draft_cache.get_seq_length(),
            start + physical_block_size,
            device=target.device,
        ).unsqueeze(0)
        noise_embedding = target.model.embed_tokens(block_ids).to(dtype=drafter_dtype)

        block_profile: dict[str, float | int] = {"block_size": physical_block_size}
        if not first_draft_recorded:
            first_draft_span.start()
        draft_span = EventSpan(enabled=profile_components)
        verify_span = EventSpan(enabled=profile_components)
        if profile_components:
            draft_span.start()
        draft_hidden = drafter(
            target_hidden=target_hidden.to(dtype=drafter_dtype),
            noise_embedding=noise_embedding,
            position_ids=positions,
            past_key_values=draft_cache,
            use_cache=True,
            is_causal=False,
        )
        stats.draft_forward_calls += 1
        draft_logits = target.lm_head(
            draft_hidden[:, 1 - physical_block_size :, :].to(dtype=target_head_dtype)
        )
        draft_cache.crop(start)
        proposed = sample(draft_logits, settings.temperature)[0, :proposal_count]
        block_ids[:, 1 : 1 + proposal_count] = proposed
        if not first_draft_recorded:
            first_draft_span.stop()
            first_draft_recorded = True
            reference_decode_span.start()
            reference_decode_started = True
        if profile_components:
            draft_span.stop()
            verify_span.start()

        verification = verifier.verify(
            block_ids=block_ids,
            start=start,
            proposal_count=proposal_count,
            full_audit=full_structural_audit,
        )
        if profile_components:
            verify_span.stop()

        stats.target_verification_calls += 1
        stats.draft_tokens_proposed += proposal_count
        stats.accepted_draft_tokens += verification.accepted_count
        stats.rollback_tokens += proposal_count - verification.accepted_count
        stats.correction_tokens += 0 if verification.all_proposals_accepted else 1
        stats.bonus_tokens += 1 if verification.all_proposals_accepted else 0
        stats.block_sizes.append(physical_block_size)

        emitted_from_block = 0
        committed_token_ids: list[int] = []
        for token_id in verification.emitted_tokens:
            if len(generated) >= settings.max_new_tokens:
                stop_reason = "max_new_tokens"
                break
            generated.append(int(token_id))
            committed_token_ids.append(int(token_id))
            emitted_from_block += 1
            stop_reason = controller.token_reason(token_id, len(generated))
            if stop_reason:
                break

        if on_tokens_committed is not None and committed_token_ids:
            decoded = tokenizer.decode(
                generated,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )
            text_delta = (
                decoded[len(streamed_text) :]
                if decoded.startswith(streamed_text)
                else tokenizer.decode(
                    committed_token_ids,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=False,
                )
            )
            streamed_text = decoded
            on_tokens_committed(committed_token_ids, text_delta)

        if emitted_from_block <= 0:
            raise RuntimeError("verification block emitted no token")
        stats.acceptance_lengths.append(emitted_from_block)
        block_policy.observe(emitted_from_block)
        if first_block_advance == 0:
            first_block_advance = emitted_from_block

        clipped = emitted_from_block != verification.raw_advance
        cache_after = (
            verifier.crop_after_boundary(
                start=start,
                accepted_count=verification.accepted_count,
                emitted_from_block=emitted_from_block,
            )
            if clipped
            else verifier.cache_length
        )
        expected_cache = (
            start + verification.raw_advance
            if not clipped
            else start + 1 + min(emitted_from_block, verification.accepted_count)
        )
        accepted_match = True
        if verification.verifier_ids is not None:
            accepted_match = (
                verification.proposals[: verification.accepted_count]
                == verification.verifier_ids[: verification.accepted_count]
            )
        structural_pass = bool(accepted_match and cache_after == expected_cache)
        if compact_structural_audit or full_structural_audit:
            audit = {
                "block_index": len(stats.structural_audit),
                "start": start,
                "proposal_count": proposal_count,
                "accepted_count": verification.accepted_count,
                "emitted_advance": emitted_from_block,
                "correction_token_id": verification.correction_token_id,
                "all_proposals_accepted": verification.all_proposals_accepted,
                "cache_length_before": verification.cache_length_before,
                "cache_length_after": cache_after,
                "expected_cache_length_after": expected_cache,
                "boundary_clipped": clipped,
                "accepted_tokens_match_target": accepted_match,
                "structural_pass": structural_pass,
            }
            if full_structural_audit:
                audit["proposal_token_ids"] = verification.proposals
                audit["verifier_token_ids"] = verification.verifier_ids
                audit["emitted_token_ids"] = verification.emitted_tokens[:emitted_from_block]
            stats.structural_audit.append(audit)
        if not structural_pass:
            raise RuntimeError(f"D-Flash structural verification failed at block {len(stats.acceptance_lengths)-1}")

        if profile_components:
            block_profile["tokens_advanced"] = emitted_from_block
            pending_block_profiles.append((block_profile, draft_span, verify_span))

        if stop_reason is None and settings.output_contract_mode == "block_boundary":
            boundary = controller.block_boundary(generated)
            if boundary.should_stop:
                stop_reason = boundary.reason
        if stop_reason is not None:
            break
        target_hidden = verification.target_hidden

    if reference_decode_started:
        reference_decode_span.stop()
    synchronize(target.device)
    for block_profile, draft_span, verify_span in pending_block_profiles:
        block_profile["draft_ms"] = float(draft_span.elapsed_ms() or 0.0)
        block_profile["verify_and_accept_ms"] = float(verify_span.elapsed_ms() or 0.0)
        stats.block_profiles.append(block_profile)
    decode_total_ms = (time.perf_counter() - decode_start) * 1000.0
    generation_total_ms = (time.perf_counter() - request_start) * 1000.0
    draft_prefill_ms = first_draft_span.elapsed_ms() if first_draft_recorded else None
    steady_state_decode_ms = (
        reference_decode_span.elapsed_ms() if reference_decode_started else None
    )
    stop, health = controller.finalize(generated, stop_reason)
    memory = collect_memory(limit_gib=memory_limit_gib)
    memory.allocated_before_bytes = memory_before["allocated_bytes"]
    memory.reserved_before_bytes = memory_before["reserved_bytes"]
    enforce_memory_gate(memory, label="D-Flash")
    return GenerationOutput(
        condition="dflash",
        text=stop.text,
        prompt_tokens=int(input_ids.shape[1]),
        output_tokens=len(generated),
        generated_token_ids=generated,
        stop_reason=stop.reason or "completed",
        timing=TimingBreakdown(
            target_prefill_ms=target_prefill_ms,
            draft_prefill_ms=draft_prefill_ms,
            decode_total_ms=decode_total_ms,
            steady_state_decode_ms=steady_state_decode_ms,
            generation_total_ms=generation_total_ms,
            warm_request_ms=generation_total_ms,
            profiling_invasive=False,
        ),
        memory=memory,
        dflash=stats,
        model=model_metadata,
        runtime={
            "output_health": health,
            "block_policy_mode": block_policy.mode,
            "rolling_tau": block_policy.rolling_tau,
            "first_block_advance": first_block_advance,
            "gpu_resident_acceptance": gpu_resident_acceptance,
            "allow_subblock_shapes": allow_subblock_shapes,
            "component_profiling_enabled": profile_components,
        },
    )
