"""Backward-compatible diagnostic alias.

Production code uses ``CachedAutoregressiveState`` or
``TargetBlockVerifierState``. This alias remains for Rec-T06A1 evidence/tests.
"""

from ccdf.inference.oracle import FullPrefixTargetOracle

TargetExecutionState = FullPrefixTargetOracle

__all__ = ["FullPrefixTargetOracle", "TargetExecutionState"]
