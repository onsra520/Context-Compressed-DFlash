from __future__ import annotations

from .base import CompressorBase


class GemmaCompressor(CompressorBase):
    def compress(self, context, question, keep_rate):
        raise NotImplementedError(
            "GemmaCompressor is reserved for a later phase and is not part of the MVP path."
        )