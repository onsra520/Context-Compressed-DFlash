"""DFlash model contract metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DFlashModelContract:
    block_size: int
    target_layer_ids: tuple[int, ...]
    mask_token_id: int
    source: str = "models/drafter/z-lab--Qwen3-4B-DFlash-b16/dflash.py"


EXPECTED_CONTRACT = DFlashModelContract(
    block_size=16,
    target_layer_ids=(1, 9, 17, 25, 33),
    mask_token_id=151669,
)
