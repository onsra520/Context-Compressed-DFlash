"""One-forward-per-block target verification with compact synchronization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from transformers import DynamicCache

from ..inference.sampling import sample
from .acceptance import AcceptanceSummary, compact_acceptance_transfer, host_acceptance_transfer


def extract_context_feature(hidden_states: tuple[torch.Tensor, ...], layer_ids: list[int]) -> torch.Tensor:
    return torch.cat([hidden_states[layer_id + 1] for layer_id in layer_ids], dim=-1)


@dataclass
class VerificationResult:
    start: int
    proposal_count: int
    accepted_count: int
    correction_token_id: int
    emitted_tokens: list[int]
    raw_advance: int
    all_proposals_accepted: bool
    cache_length_before: int
    cache_length_after: int
    target_hidden: torch.Tensor
    proposals: list[int]
    verifier_ids: list[int] | None


class TargetVerifier:
    def __init__(
        self,
        model: Any,
        input_ids: torch.Tensor,
        temperature: float,
        target_layer_ids: list[int],
        *,
        gpu_resident_acceptance: bool = True,
    ) -> None:
        self.model = model
        self.input_ids = input_ids
        self.temperature = float(temperature)
        self.target_layer_ids = [int(index) for index in target_layer_ids]
        self.gpu_resident_acceptance = bool(gpu_resident_acceptance)
        self.cache = DynamicCache()
        self.prefill_calls = 0
        self.verification_calls = 0
        self.single_token_calls = 0

    @property
    def prompt_length(self) -> int:
        return int(self.input_ids.shape[1])

    @property
    def cache_length(self) -> int:
        return int(self.cache.get_seq_length())

    @torch.inference_mode()
    def prefill(self) -> tuple[int, torch.Tensor]:
        positions = torch.arange(self.prompt_length, device=self.input_ids.device).unsqueeze(0)
        output = self.model(
            self.input_ids,
            position_ids=positions,
            past_key_values=self.cache,
            use_cache=True,
            logits_to_keep=1,
            output_hidden_states=True,
        )
        self.prefill_calls += 1
        seed = int(sample(output.logits, self.temperature)[0, -1].item())
        hidden = extract_context_feature(output.hidden_states, self.target_layer_ids)
        if self.cache_length != self.prompt_length:
            raise RuntimeError(
                f"target prefill cache length {self.cache_length} != prompt length {self.prompt_length}"
            )
        return seed, hidden

    @torch.inference_mode()
    def verify(
        self,
        *,
        block_ids: torch.Tensor,
        start: int,
        proposal_count: int,
        full_audit: bool,
    ) -> VerificationResult:
        if self.cache_length != start:
            raise RuntimeError(f"target cache length {self.cache_length} != block start {start}")
        before = self.cache_length
        positions = torch.arange(start, start + block_ids.shape[1], device=block_ids.device).unsqueeze(0)
        output = self.model(
            block_ids,
            position_ids=positions,
            past_key_values=self.cache,
            use_cache=True,
            output_hidden_states=True,
        )
        self.verification_calls += 1
        posterior_ids = sample(output.logits, self.temperature)[0]
        proposed = block_ids[0, 1 : 1 + proposal_count]
        transfer = compact_acceptance_transfer if self.gpu_resident_acceptance else host_acceptance_transfer
        summary: AcceptanceSummary = transfer(
            proposals=proposed,
            posterior_ids=posterior_ids,
            full_audit=full_audit,
            correction_logits=output.logits[0],
            temperature=self.temperature,
        )
        accepted = int(summary.accepted_count)
        emitted = summary.proposals[:accepted] + [int(summary.correction_token_id)]
        raw_advance = len(emitted)
        new_start = start + raw_advance
        self.cache.crop(new_start)
        hidden = extract_context_feature(output.hidden_states, self.target_layer_ids)[:, : accepted + 1, :]
        return VerificationResult(
            start=start,
            proposal_count=proposal_count,
            accepted_count=accepted,
            correction_token_id=int(summary.correction_token_id),
            emitted_tokens=emitted,
            raw_advance=raw_advance,
            all_proposals_accepted=accepted == proposal_count,
            cache_length_before=before,
            cache_length_after=self.cache_length,
            target_hidden=hidden,
            proposals=summary.proposals,
            verifier_ids=summary.verifier_ids,
        )

    def crop_after_boundary(self, *, start: int, accepted_count: int, emitted_from_block: int) -> int:
        retained_proposals = min(max(int(emitted_from_block), 0), int(accepted_count))
        keep = int(start) + 1 + retained_proposals
        self.cache.crop(keep)
        return self.cache_length
