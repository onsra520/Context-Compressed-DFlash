"""Efficient one-target-forward-per-block verification state.

The implementation follows the pinned drafter's ``spec_generate`` cache and
position semantics while exposing structural audit data required by the NF4
claim boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch

from ccdf.dflash.utils import acceptance_prefix_length, extract_context_feature, sample


@dataclass
class VerificationBlockResult:
    start: int
    proposal_count: int
    proposals: list[int]
    verifier_argmax_ids: list[int]
    accepted_count: int
    first_mismatch_index: int | None
    correction_token_id: int
    all_proposals_accepted: bool
    raw_emitted_tokens: list[int]
    raw_advance: int
    cache_length_before: int
    cache_length_after: int
    cache_positions: list[int]
    target_hidden: Any
    target_output: Any


class TargetBlockVerifierState:
    """Target cache authority for production DFlash block verification."""

    def __init__(self, model, input_ids: torch.Tensor, temperature: float, target_layer_ids: list[int]) -> None:
        self.model = model
        self.input_ids = input_ids
        self.temperature = temperature
        self.target_layer_ids = target_layer_ids
        from transformers import DynamicCache
        self.cache = DynamicCache()
        self.target_prefill_calls = 0
        self.target_block_verification_calls = 0
        self.target_single_token_fallback_calls = 0
        self.target_hidden_refresh_calls = 0

    @property
    def prompt_length(self) -> int:
        return int(self.input_ids.shape[1])

    @property
    def cache_length(self) -> int:
        return int(self.cache.get_seq_length())

    @property
    def total_target_forward_calls(self) -> int:
        return (
            self.target_prefill_calls
            + self.target_block_verification_calls
            + self.target_single_token_fallback_calls
            + self.target_hidden_refresh_calls
        )

    @torch.inference_mode()
    def prefill(self) -> tuple[int, Any]:
        positions = torch.arange(self.prompt_length, device=self.input_ids.device).unsqueeze(0)
        output = self.model(
            self.input_ids,
            position_ids=positions,
            past_key_values=self.cache,
            use_cache=True,
            logits_to_keep=1,
            output_hidden_states=True,
        )
        self.target_prefill_calls += 1
        seed = int(sample(output.logits, self.temperature)[0, -1].item())
        target_hidden = extract_context_feature(output.hidden_states, self.target_layer_ids)
        if self.cache_length != self.prompt_length:
            raise RuntimeError(
                f"target prefill cache length {self.cache_length} != prompt length {self.prompt_length}"
            )
        return seed, target_hidden

    @torch.inference_mode()
    def verify(
        self,
        *,
        block_ids: torch.Tensor,
        start: int,
        proposal_count: int,
    ) -> VerificationBlockResult:
        if self.cache_length != start:
            raise RuntimeError(
                f"target cache length {self.cache_length} does not match block start {start}"
            )
        if block_ids.ndim != 2 or block_ids.shape[0] != 1:
            raise ValueError("block_ids must have shape [1, block]")
        if proposal_count < 0 or proposal_count > block_ids.shape[1] - 1:
            raise ValueError("invalid proposal_count")

        cache_before = self.cache_length
        positions = torch.arange(start, start + block_ids.shape[1], device=block_ids.device).unsqueeze(0)
        output = self.model(
            block_ids,
            position_ids=positions,
            past_key_values=self.cache,
            use_cache=True,
            output_hidden_states=True,
        )
        self.target_block_verification_calls += 1
        posterior = sample(output.logits, self.temperature)[0].detach().cpu().tolist()
        proposals = block_ids[0, 1 : 1 + proposal_count].detach().cpu().tolist()
        verifier_for_proposals = posterior[:proposal_count]
        accepted = acceptance_prefix_length(proposals, verifier_for_proposals)
        correction = int(posterior[accepted])
        all_accepted = accepted == proposal_count
        raw_tokens = [int(token) for token in proposals[:accepted]] + [correction]
        raw_advance = len(raw_tokens)

        # Same crop boundary as the pinned upstream spec_generate path. The
        # correction/bonus token is emitted but becomes the first input token
        # of the next block; it is intentionally not retained in target KV.
        new_start = start + raw_advance
        self.cache.crop(new_start)
        target_hidden = extract_context_feature(output.hidden_states, self.target_layer_ids)[
            :, : accepted + 1, :
        ]
        return VerificationBlockResult(
            start=start,
            proposal_count=proposal_count,
            proposals=[int(token) for token in proposals],
            verifier_argmax_ids=[int(token) for token in verifier_for_proposals],
            accepted_count=accepted,
            first_mismatch_index=None if all_accepted else accepted,
            correction_token_id=correction,
            all_proposals_accepted=all_accepted,
            raw_emitted_tokens=raw_tokens,
            raw_advance=raw_advance,
            cache_length_before=cache_before,
            cache_length_after=self.cache_length,
            cache_positions=list(range(start, start + int(block_ids.shape[1]))),
            target_hidden=target_hidden,
            target_output=output,
        )

    def crop_after_boundary(self, *, start: int, accepted_count: int, emitted_from_block: int) -> int:
        """Crop a verified block when EOS/output-contract/cap clips emission."""

        retained_proposals = min(max(emitted_from_block, 0), accepted_count)
        keep = start + 1 + retained_proposals
        self.cache.crop(keep)
        return self.cache_length
