from __future__ import annotations

from importlib import import_module
from typing import Protocol

_types = import_module("htfsd_types")
TokenResult = _types.TokenResult
VerificationResult = _types.VerificationResult


class GemmaE2BVerifier(Protocol):
    def verify_greedy_prefix(
        self,
        context_token_ids: list[int],
        candidate_token_ids: list[int],
    ) -> VerificationResult:
        ...

    def greedy_next_token(self, context_token_ids: list[int]) -> TokenResult:
        ...
