"""Compression architecture.

Heavy LLMLingua/Transformers dependencies are imported only when the real
compressor is instantiated.
"""

from ccdf.compression.passthrough import PassthroughCompressor

__all__ = ["PassthroughCompressor", "LLMLinguaCompressor"]


def __getattr__(name: str):
    if name == "LLMLinguaCompressor":
        from ccdf.compression.llmlingua import LLMLinguaCompressor

        return LLMLinguaCompressor
    raise AttributeError(name)
