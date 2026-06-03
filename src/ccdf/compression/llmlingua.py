from __future__ import annotations

from .base import CompressorBase


class LlmlinguaCompressor(CompressorBase):
    def compress(self, context, question, keep_rate):
        raise NotImplementedError(
            "LlmlinguaCompressor is only a skeleton until the MVP compression path is wired."
        )