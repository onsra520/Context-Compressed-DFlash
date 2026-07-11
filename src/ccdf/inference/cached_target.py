"""Standard cached autoregressive target execution for Baseline-AR."""

from __future__ import annotations

import torch

from ccdf.dflash.utils import sample


class CachedAutoregressiveState:
    def __init__(self, model, input_ids: torch.Tensor, temperature: float) -> None:
        self.model = model
        self.input_ids = input_ids
        self.temperature = temperature
        from transformers import DynamicCache
        self.cache = DynamicCache()
        self.generated: list[int] = []
        self.target_forward_calls = 0
        self.last_output = None

    @property
    def prompt_length(self) -> int:
        return int(self.input_ids.shape[1])

    @property
    def cache_length(self) -> int:
        return int(self.cache.get_seq_length())

    @torch.inference_mode()
    def prefill(self) -> int:
        positions = torch.arange(self.prompt_length, device=self.input_ids.device).unsqueeze(0)
        self.last_output = self.model(
            self.input_ids,
            position_ids=positions,
            attention_mask=torch.ones_like(self.input_ids),
            past_key_values=self.cache,
            use_cache=True,
            logits_to_keep=1,
            output_hidden_states=False,
        )
        self.target_forward_calls += 1
        return int(sample(self.last_output.logits, self.temperature)[0, -1].item())

    @torch.inference_mode()
    def next_token(self, committed_token: int) -> int:
        position = self.prompt_length + len(self.generated) - 1
        token = torch.tensor([[int(committed_token)]], device=self.input_ids.device, dtype=torch.long)
        attention = torch.ones((1, position + 1), device=self.input_ids.device, dtype=torch.long)
        position_ids = torch.tensor([[position]], device=self.input_ids.device, dtype=torch.long)
        self.last_output = self.model(
            token,
            position_ids=position_ids,
            attention_mask=attention,
            past_key_values=self.cache,
            use_cache=True,
            logits_to_keep=1,
            output_hidden_states=False,
        )
        self.target_forward_calls += 1
        return int(sample(self.last_output.logits, self.temperature)[0, -1].item())

    def commit(self, token_id: int) -> None:
        self.generated.append(int(token_id))

    def diagnostic_state(self) -> dict[str, object]:
        absolute = self.prompt_length + len(self.generated)
        return {
            "cache_sequence_length": self.cache_length,
            "committed_sequence_length": absolute,
            "position_ids": [absolute - 1] if absolute else [],
        }
