"""Prompt fixture loading for smoke and benchmark runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_prompt_fixtures(path: str | Path) -> list[dict[str, Any]]:
    """Load JSONL prompt fixtures with normalized field types."""

    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            rows.append(
                {
                    "id": str(payload["id"]),
                    "prompt": str(payload["prompt"]),
                    "max_new_tokens": int(payload.get("max_new_tokens", 128)),
                }
            )
    return rows
