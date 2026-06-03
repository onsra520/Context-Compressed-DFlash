from __future__ import annotations

from .base import CompressorBase


class PassthroughCompressor(CompressorBase):
    def compress(self, context, question, keep_rate):
        context_text = context if isinstance(context, str) else str(context)
        info = {
            "t_compress_ms": 0.0,
            "R_actual": 1.0,
            "N_original": len(context_text),
            "N_compressed": len(context_text),
            "keep_rate": keep_rate,
            "strategy": "passthrough",
        }
        return context_text, info