"""Diagnostic full-prefix target oracle from Rec-T06A1.

This module must never be imported by production Baseline/DFlash dispatch.
"""

from __future__ import annotations

import torch

from ccdf.dflash.utils import sample


class FullPrefixTargetOracle:
    def __init__(self, model, input_ids: torch.Tensor, temperature: float) -> None:
        self.model = model
        self.input_ids = input_ids
        self.temperature = temperature
        self.emitted: list[int] = []
        self.last_output = None

    @property
    def prompt_length(self) -> int:
        return int(self.input_ids.shape[1])

    def _sequence(self) -> torch.Tensor:
        if not self.emitted:
            return self.input_ids
        suffix = torch.tensor([self.emitted], device=self.input_ids.device, dtype=torch.long)
        return torch.cat([self.input_ids, suffix], dim=1)

    @torch.inference_mode()
    def forward(self, *, output_hidden_states: bool = False):
        sequence = self._sequence()
        positions = torch.arange(sequence.shape[1], device=sequence.device).unsqueeze(0)
        self.last_output = self.model(
            sequence,
            position_ids=positions,
            attention_mask=torch.ones_like(sequence),
            use_cache=False,
            logits_to_keep=1,
            output_hidden_states=output_hidden_states,
        )
        return self.last_output

    def next_token(self, *, output_hidden_states: bool = False) -> int:
        output = self.forward(output_hidden_states=output_hidden_states)
        return int(sample(output.logits, self.temperature)[0, -1].item())

    def commit(self, token_id: int) -> None:
        self.emitted.append(int(token_id))
    def diagnostic_state(self) -> dict[str, object]:
        sequence_length = self.prompt_length + len(self.emitted)
        return {
            "cache_sequence_length": 0,
            "input_length": sequence_length,
            "attention_mask_length": sequence_length,
            "position_ids": [sequence_length - 1] if sequence_length else [],
            "cache_position": None,
        }

