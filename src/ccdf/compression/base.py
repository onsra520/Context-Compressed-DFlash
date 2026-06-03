from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CompressorBase(ABC):
    @abstractmethod
    def compress(self, context: Any, question: Any, keep_rate: float):
        raise NotImplementedError