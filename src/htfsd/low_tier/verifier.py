from __future__ import annotations

from typing import Protocol

from htfsd.types import TokenResult, VerificationResult


class GemmaE2BVerifier(Protocol):
    def verify_greedy_prefix(
        self,
        context_token_ids: list[int],
        candidate_token_ids: list[int],
    ) -> VerificationResult:
        ...

    def greedy_next_token(self, context_token_ids: list[int]) -> TokenResult:
        ...
