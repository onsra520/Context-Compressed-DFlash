from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunRequest:
    source_type: str
    condition: str
    prompt: str
    prompt_profile: str = "raw"
    schema_version: str = "cc_dflash_demo_v1"
    dataset: str | None = None
    split: str | None = None
    fixture_id: str | int | None = None
    reference_answer: str | None = None
    max_new_tokens: int = 128
    seed: int = 42
    generation_options: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
