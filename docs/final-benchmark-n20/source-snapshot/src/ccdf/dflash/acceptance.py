"""GPU-resident accepted-prefix calculation."""

from __future__ import annotations

from dataclasses import dataclass

import torch

from ..inference.sampling import sample_verifier_logits


@dataclass(frozen=True)
class AcceptanceSummary:
    accepted_count: int
    correction_token_id: int
    proposals: list[int]
    verifier_ids: list[int] | None


def accepted_prefix_tensor(proposals: torch.Tensor, verifier_ids: torch.Tensor) -> torch.Tensor:
    if proposals.ndim != 1 or verifier_ids.ndim != 1:
        raise ValueError("proposals and verifier_ids must be one-dimensional")
    if proposals.shape != verifier_ids.shape:
        raise ValueError("proposals and verifier_ids must have the same shape")
    if proposals.numel() == 0:
        return torch.zeros((), device=proposals.device, dtype=torch.long)
    matches = proposals.eq(verifier_ids)
    return matches.to(torch.long).cumprod(dim=0).sum()


def compact_acceptance_transfer(
    *,
    proposals: torch.Tensor,
    posterior_ids: torch.Tensor,
    full_audit: bool,
    correction_logits: torch.Tensor | None = None,
    temperature: float = 0.0,
) -> AcceptanceSummary:
    """Compute the prefix on GPU and perform one compact host transfer per block."""
    verifier_ids = posterior_ids[: proposals.numel()]
    accepted = accepted_prefix_tensor(proposals, verifier_ids)
    correction = (
        sample_verifier_logits(
            correction_logits.index_select(0, accepted.reshape(1)), temperature
        ).reshape(())
        if correction_logits is not None
        else posterior_ids.gather(0, accepted.reshape(1))[0]
    )
    payload = [accepted.reshape(1), correction.reshape(1), proposals.to(torch.long)]
    if full_audit:
        payload.append(verifier_ids.to(torch.long))
    host = torch.cat(payload).detach().cpu().tolist()
    accepted_count = int(host[0])
    correction_token_id = int(host[1])
    count = int(proposals.numel())
    proposal_ids = [int(value) for value in host[2 : 2 + count]]
    audit_ids = [int(value) for value in host[2 + count : 2 + count * 2]] if full_audit else None
    return AcceptanceSummary(accepted_count, correction_token_id, proposal_ids, audit_ids)


def host_acceptance_transfer(
    *,
    proposals: torch.Tensor,
    posterior_ids: torch.Tensor,
    full_audit: bool,
    correction_logits: torch.Tensor | None = None,
    temperature: float = 0.0,
) -> AcceptanceSummary:
    """Reference-style host acceptance path retained for controlled ablation."""
    proposal_ids = [int(value) for value in proposals.detach().cpu().tolist()]
    posterior_host = [int(value) for value in posterior_ids.detach().cpu().tolist()]
    accepted = 0
    for proposal, target in zip(proposal_ids, posterior_host[: len(proposal_ids)]):
        if proposal != target:
            break
        accepted += 1
    correction = (
        int(
            sample_verifier_logits(
                correction_logits[accepted : accepted + 1], temperature
            )[0].item()
        )
        if correction_logits is not None
        else int(posterior_host[accepted])
    )
    verifier = posterior_host[: len(proposal_ids)] if full_audit else None
    return AcceptanceSummary(accepted, correction, proposal_ids, verifier)
