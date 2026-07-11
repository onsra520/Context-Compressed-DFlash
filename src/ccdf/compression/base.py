"""Compressor interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ccdf.compression.schemas import CompressionConfig, CompressionResult


class CompressorBase(ABC):
    @abstractmethod
    def compress(
        self, *, context: str, question: str, config: CompressionConfig
    ) -> CompressionResult:
        raise NotImplementedError
