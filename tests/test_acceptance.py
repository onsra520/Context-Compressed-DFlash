import torch

from ccdf.dflash.acceptance import accepted_prefix_tensor, compact_acceptance_transfer, host_acceptance_transfer


def test_accepted_prefix_full_match():
    proposals = torch.tensor([1, 2, 3, 4])
    verifier = torch.tensor([1, 2, 3, 4])
    assert accepted_prefix_tensor(proposals, verifier).item() == 4


def test_accepted_prefix_stops_at_first_mismatch():
    proposals = torch.tensor([1, 2, 9, 4])
    posterior = torch.tensor([1, 2, 3, 8, 7])
    summary = compact_acceptance_transfer(
        proposals=proposals,
        posterior_ids=posterior,
        full_audit=True,
    )
    assert summary.accepted_count == 2
    assert summary.correction_token_id == 3
    assert summary.proposals == [1, 2, 9, 4]
    assert summary.verifier_ids == [1, 2, 3, 8]


def test_host_ablation_matches_compact_path():
    proposals = torch.tensor([4, 5, 9])
    posterior = torch.tensor([4, 5, 6, 7])
    compact = compact_acceptance_transfer(proposals=proposals, posterior_ids=posterior, full_audit=True)
    host = host_acceptance_transfer(proposals=proposals, posterior_ids=posterior, full_audit=True)
    assert host == compact
