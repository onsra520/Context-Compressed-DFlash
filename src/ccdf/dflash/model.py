from __future__ import annotations

# STATUS: skeleton-only placeholder. Do not treat this as the upstream DFlash implementation.

from dataclasses import dataclass, field


@dataclass
class DFlashDraftModel:
    block_size: int = 16
    mask_token_id: int | None = None
    target_layer_ids: list[int] = field(default_factory=list)

    @classmethod
    def from_pretrained(cls, *args, **kwargs):
        raise NotImplementedError(
            "DFlashDraftModel still points to the upstream reference implementation."
        )