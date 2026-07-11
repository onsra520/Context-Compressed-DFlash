"""DFlash utility functions audited from local drafter source."""

from __future__ import annotations

from typing import Iterable


def build_target_layer_ids(num_target_layers: int, num_draft_layers: int) -> list[int]:
    if num_draft_layers == 1:
        return [num_target_layers // 2]
    start = 1
    end = num_target_layers - 3
    span = end - start
    return [int(round(start + (i * span) / (num_draft_layers - 1))) for i in range(num_draft_layers)]


def acceptance_prefix_length(draft_tokens: Iterable[int], target_tokens: Iterable[int]) -> int:
    count = 0
    for draft, target in zip(draft_tokens, target_tokens):
        if draft != target:
            break
        count += 1
    return count


def metric_counters(acceptance_lengths: list[int], draft_tokens_proposed: int) -> dict[str, float | int]:
    verification_calls = len(acceptance_lengths)
    tokens_advanced = sum(acceptance_lengths)
    accepted_draft_tokens = tokens_advanced - verification_calls if verification_calls else 0
    rollback_tokens = draft_tokens_proposed - accepted_draft_tokens
    return {
        "verification_calls": verification_calls,
        "tau_tokens_advanced_per_verification": tokens_advanced / verification_calls
        if verification_calls
        else 0.0,
        "accepted_draft_tokens": accepted_draft_tokens,
        "rollback_tokens": rollback_tokens,
    }


def sample(logits, temperature: float = 0.0):
    import torch

    if temperature < 1e-5:
        return torch.argmax(logits, dim=-1)
    bsz, seq_len, vocab_size = logits.shape
    probs = torch.softmax((logits.view(-1, vocab_size) / temperature), dim=-1)
    return torch.multinomial(probs, num_samples=1).view(bsz, seq_len)


def extract_context_feature(hidden_states, layer_ids: list[int]):
    import torch

    return torch.cat([hidden_states[layer_id + 1] for layer_id in layer_ids], dim=-1)
