"""Protocols for a future feature-level high-tier implementation."""

from __future__ import annotations

from typing import Protocol


class FeatureDrafter(Protocol):
    """Future Gemma E2B feature drafter contract."""

    def draft_features(self, prompt: str):
        """Return backend-specific intermediate features for high-tier use."""

        raise NotImplementedError


class FeatureVerifier(Protocol):
    """Future Gemma E4B feature verifier contract."""

    def verify_features(self, features):
        """Verify backend-specific intermediate features."""

        raise NotImplementedError
