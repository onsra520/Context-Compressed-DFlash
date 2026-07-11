"""Compression architecture reconstructed for Rec-T04A."""

from ccdf.compression.passthrough import PassthroughCompressor
from ccdf.compression.llmlingua import LLMLinguaCompressor

__all__ = ["PassthroughCompressor", "LLMLinguaCompressor"]
