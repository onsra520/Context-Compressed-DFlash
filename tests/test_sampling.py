import torch

from ccdf.inference import sampling
from ccdf.dflash.acceptance import compact_acceptance_transfer


def test_verifier_greedy_uses_lowest_id_for_exact_maximum_tie() -> None:
    logits = torch.tensor([[[0.0, 2.0, 1.0, 2.0]]], dtype=torch.float16)
    assert sampling.sample_verifier_logits(logits).item() == 1


def test_verifier_greedy_treats_previous_fp16_value_as_tie_band() -> None:
    logits = torch.tensor([[[0.0, 37.25, 1.0, 37.28125]]], dtype=torch.float16)
    assert sampling.sample_verifier_logits(logits).item() == 1


def test_verifier_greedy_keeps_winner_beyond_one_ulp() -> None:
    logits = torch.tensor([[[0.0, 37.21875, 1.0, 37.28125]]], dtype=torch.float16)
    assert sampling.sample_verifier_logits(logits).item() == 3


def test_verifier_stochastic_path_delegates_to_existing_sampler(monkeypatch) -> None:
    expected = torch.tensor([[2]])
    monkeypatch.setattr(sampling, "sample", lambda logits, temperature: expected)
    actual = sampling.sample_verifier_logits(torch.zeros((1, 1, 4)), temperature=0.5)
    assert actual is expected


def test_compact_acceptance_applies_tie_band_only_to_correction_row() -> None:
    proposals = torch.tensor([5, 6])
    posterior = torch.tensor([5, 3, 0])
    correction_logits = torch.tensor(
        [
            [0.0, 1.0, 0.0, 2.0, 0.0, 3.0, 0.0],
            [0.0, 37.25, 0.0, 37.28125, 0.0, 0.0, 0.0],
            [3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ],
        dtype=torch.float16,
    )
    result = compact_acceptance_transfer(
        proposals=proposals,
        posterior_ids=posterior,
        full_audit=True,
        correction_logits=correction_logits,
    )
    assert result.accepted_count == 1
    assert result.correction_token_id == 1
    assert result.verifier_ids == [5, 3]
