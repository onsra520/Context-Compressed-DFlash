from __future__ import annotations

__all__ = [
    "CompressorBase",
    "PassthroughCompressor",
    "load_config",
    "resolve_compressor_model_source",
    "resolve_llmlingua_config",
    "merge",
    "segment_gsm8k",
]


def __getattr__(name: str):
    if name == "load_config":
        from .config.loader import load_config

        return load_config
    if name == "resolve_llmlingua_config":
        from .config.loader import resolve_llmlingua_config

        return resolve_llmlingua_config
    if name == "resolve_compressor_model_source":
        from .config.loader import resolve_compressor_model_source

        return resolve_compressor_model_source
    if name == "CompressorBase":

        from .compression.base import CompressorBase

        return CompressorBase
    if name == "PassthroughCompressor":
        from .compression.passthrough import PassthroughCompressor

        return PassthroughCompressor
    if name in {"segment_gsm8k", "merge"}:
        from .compression.segmentation import merge, segment_gsm8k

        return {"segment_gsm8k": segment_gsm8k, "merge": merge}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
