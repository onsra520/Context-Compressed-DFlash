from __future__ import annotations

from typing import Any


def benchmark_error_row(
    *,
    prompt_id: str,
    error: Exception,
    prompt: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "prompt_id": prompt_id,
        "status": "error",
        "error": str(error),
    }
    if prompt is not None:
        row["prompt"] = prompt
    return row
