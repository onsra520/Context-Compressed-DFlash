from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CCDFlashPipeline:
    compressor: Any
    dflash: Any
    tokenizer: Any | None = None

    def describe(self) -> dict[str, Any]:
        return {
            "compression": type(self.compressor).__name__,
            "dflash": type(self.dflash).__name__,
            "tokenizer": None if self.tokenizer is None else type(self.tokenizer).__name__,
        }

    def run(self, *args, **kwargs):
        raise NotImplementedError(
            "CCDFlashPipeline is wired structurally only; execution will be added after upstream code split."
        )