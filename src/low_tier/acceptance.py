from __future__ import annotations

from importlib import import_module

_types = import_module("htfsd_types")
VerificationResult = _types.VerificationResult


def greedy_exact_match(
    *,
    candidate_token_ids: list[int],
    greedy_token_ids: list[int],
) -> VerificationResult:
    accepted: list[int] = []
    for index, candidate_token_id in enumerate(candidate_token_ids):
        if index >= len(greedy_token_ids):
            return VerificationResult(
                accepted_token_ids=accepted,
                rejected_token_id=candidate_token_id,
                reject_position=index,
                candidate_exhausted=False,
            )
        if candidate_token_id != greedy_token_ids[index]:
            return VerificationResult(
                accepted_token_ids=accepted,
                rejected_token_id=candidate_token_id,
                reject_position=index,
                candidate_exhausted=False,
            )
        accepted.append(candidate_token_id)

    return VerificationResult(
        accepted_token_ids=accepted,
        rejected_token_id=None,
        reject_position=None,
        candidate_exhausted=True,
    )
