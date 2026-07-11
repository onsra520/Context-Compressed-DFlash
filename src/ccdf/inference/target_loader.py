"""Local-only target model loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_target_tokenizer(path: Path):
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=True)


def load_target_model(path: Path, *, device_map: str = "auto") -> Any:
    import torch
    from transformers import AutoModelForCausalLM

    return AutoModelForCausalLM.from_pretrained(
        path,
        local_files_only=True,
        device_map=device_map,
        dtype=torch.bfloat16,
    )


def load_target_config(path: Path):
    from transformers import AutoConfig

    return AutoConfig.from_pretrained(path, local_files_only=True, trust_remote_code=True)
