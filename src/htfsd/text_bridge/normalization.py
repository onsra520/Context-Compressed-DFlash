"""Normalization for raw Qwen draft text before Gemma use."""

from __future__ import annotations

import re

from htfsd.types import BridgeDraft

THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


def normalize_qwen_draft(raw_text: str) -> BridgeDraft:
    """Normalize a raw Qwen draft for the cross-family text bridge."""

    if _has_unclosed_think(raw_text):
        return BridgeDraft(
            bridge_status="rejected",
            normalized_text="",
            rejection_reason="contains_unclosed_think",
        )
    normalized = THINK_BLOCK_PATTERN.sub("", raw_text).strip()
    if not normalized:
        return BridgeDraft(
            bridge_status="rejected",
            normalized_text="",
            rejection_reason="empty_after_normalization",
        )
    return BridgeDraft(
        bridge_status="valid",
        normalized_text=normalized,
        rejection_reason=None,
    )


def _has_unclosed_think(text: str) -> bool:
    lower_text = text.lower()
    return "<think>" in lower_text and "</think>" not in lower_text
