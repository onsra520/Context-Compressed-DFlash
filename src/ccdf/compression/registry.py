"""Compressor registry."""

from __future__ import annotations

from ccdf.compression.llmlingua import LLMLinguaCompressor
from ccdf.compression.passthrough import PassthroughCompressor


def get_compressor(name: str):
    if name == "passthrough":
        return PassthroughCompressor()
    if name == "llmlingua":
        return LLMLinguaCompressor()
    raise ValueError(f"unknown compressor: {name}")
