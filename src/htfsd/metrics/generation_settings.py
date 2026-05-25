"""Controlled generation settings for trace runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from htfsd.types import HTFSDConfig


DEFAULT_OUTPUT_SUMMARY_MAX_CHARS = 120


@dataclass(frozen=True)
class GenerationSettings:
    """Generation settings shared by low-tier and baseline traces."""

    max_tokens: int
    temperature: float
    seed: int
    stop: list[str] | None = None
    prompt_mode: str = "raw"
    capture_raw_output: bool = False
    output_summary_max_chars: int = DEFAULT_OUTPUT_SUMMARY_MAX_CHARS

    def to_metadata(self) -> dict[str, Any]:
        """Return a JSON-friendly settings snapshot."""

        return asdict(self)


def build_generation_settings(
    config: HTFSDConfig,
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    stop: list[str] | None = None,
    prompt_mode: str = "raw",
    capture_raw_output: bool = False,
    output_summary_max_chars: int = DEFAULT_OUTPUT_SUMMARY_MAX_CHARS,
) -> GenerationSettings:
    """Build trace settings from config plus explicit CLI overrides."""

    if prompt_mode not in {"raw", "chat"}:
        raise ValueError(f"Unsupported prompt_mode: {prompt_mode}")

    return GenerationSettings(
        max_tokens=int(max_tokens if max_tokens is not None else config.generation.max_tokens),
        temperature=float(temperature if temperature is not None else config.generation.temperature),
        seed=config.runtime.seed,
        stop=stop,
        prompt_mode=prompt_mode,
        capture_raw_output=capture_raw_output,
        output_summary_max_chars=output_summary_max_chars,
    )
