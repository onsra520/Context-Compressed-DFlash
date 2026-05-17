from __future__ import annotations

import json
from typing import Any

from htfsd.types import DFlashParseResult


def _normalize_draft_text(value: str) -> str:
    return value.replace("\r\n", "\n").strip()


def parse_dflash(raw_text: str) -> DFlashParseResult:
    try:
        payload: Any = json.loads(raw_text)
    except json.JSONDecodeError:
        return DFlashParseResult(
            draft_text=None,
            confidence=None,
            max_tokens=None,
            parse_ok=False,
            error_reason="parse_fail",
        )

    if not isinstance(payload, dict):
        return DFlashParseResult(None, None, None, False, "schema_invalid")

    draft_value = payload.get("draft_text")
    if not isinstance(draft_value, str):
        return DFlashParseResult(None, None, None, False, "schema_invalid")

    draft_text = _normalize_draft_text(draft_value)
    if not draft_text:
        return DFlashParseResult(None, None, None, False, "empty_draft")

    confidence = payload.get("confidence")
    if confidence is not None:
        if not isinstance(confidence, int | float) or not 0.0 <= float(confidence) <= 1.0:
            return DFlashParseResult(None, None, None, False, "schema_invalid")
        confidence = float(confidence)

    max_tokens = payload.get("max_tokens")
    if max_tokens is not None:
        if not isinstance(max_tokens, int) or max_tokens < 0:
            return DFlashParseResult(None, None, None, False, "schema_invalid")

    return DFlashParseResult(
        draft_text=draft_text,
        confidence=confidence,
        max_tokens=max_tokens,
        parse_ok=True,
        error_reason=None,
    )
