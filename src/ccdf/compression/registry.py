"""Compressor registry."""

from __future__ import annotations

from ccdf.compression.llmlingua import LLMLinguaCompressor
from ccdf.compression.passthrough import PassthroughCompressor


def get_compressor(name: str, *, model_path=None, device_map: str = "cpu"):
    if name == "passthrough":
        return PassthroughCompressor()
    if name == "llmlingua":
        if model_path is None:
            return LLMLinguaCompressor(device_map=device_map)
        return LLMLinguaCompressor(model_path=model_path, device_map=device_map)
    raise ValueError(f"unknown compressor: {name}")
