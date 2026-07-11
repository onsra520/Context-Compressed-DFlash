from types import SimpleNamespace

import torch

from ccdf.inference.target_execution import TargetExecutionState


class DeterministicTarget:
    """Records the canonical call contract without requiring a checkpoint."""

    def __init__(self):
        self.calls = []

    def __call__(self, input_ids, **kwargs):
        self.calls.append((input_ids.clone(), kwargs))
        logits = torch.zeros((1, input_ids.shape[1], 8))
        logits[:, -1, input_ids.shape[1] % 8] = 1.0
        return SimpleNamespace(logits=logits, hidden_states=(torch.zeros((1, input_ids.shape[1], 2)),))


def test_target_execution_uses_complete_prefix_without_cache() -> None:
    model = DeterministicTarget()
    state = TargetExecutionState(model, torch.tensor([[2, 3, 4]]), 0.0)

    assert state.next_token() == 3
    state.commit(3)
    assert state.next_token() == 4

    first_ids, first = model.calls[0]
    second_ids, second = model.calls[1]
    assert first_ids.tolist() == [[2, 3, 4]]
    assert second_ids.tolist() == [[2, 3, 4, 3]]
    assert first["use_cache"] is False
    assert second["use_cache"] is False
    assert first["attention_mask"].tolist() == [[1, 1, 1]]
    assert second["position_ids"].tolist() == [[0, 1, 2, 3]]
    assert state.diagnostic_state()["cache_sequence_length"] == 0
