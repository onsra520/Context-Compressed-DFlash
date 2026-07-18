"""Deterministic and stochastic token selection."""

from __future__ import annotations

import torch


def sample(logits: torch.Tensor, temperature: float = 0.0) -> torch.Tensor:
    if temperature < 1e-5:
        return torch.argmax(logits, dim=-1)
    batch, sequence, vocab = logits.shape
    probs = torch.softmax(logits.reshape(-1, vocab) / temperature, dim=-1)
    return torch.multinomial(probs, num_samples=1).reshape(batch, sequence)
