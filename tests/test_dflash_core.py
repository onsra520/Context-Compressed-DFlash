from __future__ import annotations

import torch

from ccdf.dflash.utils import build_target_layer_ids, extract_context_feature, sample


def test_build_target_layer_ids_matches_reference_spacing():
    assert build_target_layer_ids(12, 3) == [1, 5, 9]


def test_extract_context_feature_uses_layer_offset():
    hidden_states = [
        torch.tensor([[0.0, 0.0]]),
        torch.tensor([[1.0, 1.0]]),
        torch.tensor([[2.0, 2.0]]),
        torch.tensor([[3.0, 3.0]]),
    ]
    feature = extract_context_feature(hidden_states, [0, 1])
    assert torch.equal(feature, torch.tensor([[1.0, 1.0, 2.0, 2.0]]))


def test_sample_greedy_path_chooses_argmax():
    logits = torch.tensor([[[1.0, 5.0, 2.0]]])
    assert torch.equal(sample(logits, temperature=0.0), torch.tensor([[1]]))