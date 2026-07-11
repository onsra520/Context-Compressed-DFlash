"""Local-only drafter loading and compatibility checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_drafter_config(path: Path):
    from transformers import AutoConfig

    return AutoConfig.from_pretrained(path, local_files_only=True, trust_remote_code=True)


def load_drafter_model(path: Path, *, device_map: str = "auto") -> Any:
    import torch
    from transformers import AutoModel

    return AutoModel.from_pretrained(
        path,
        local_files_only=True,
        trust_remote_code=True,
        dtype=torch.bfloat16,
        device_map=device_map,
    )


def audit_model_contract(target_config: Any, drafter_config: Any) -> dict[str, Any]:
    checks = {
        "hidden_size_match": target_config.hidden_size == drafter_config.hidden_size,
        "vocab_size_match": target_config.vocab_size == drafter_config.vocab_size,
        "target_layers": list(drafter_config.dflash_config["target_layer_ids"]),
        "block_size": drafter_config.block_size,
        "num_target_layers_match": drafter_config.num_target_layers == target_config.num_hidden_layers,
        "enable_thinking": False,
    }
    checks["pass"] = (
        checks["hidden_size_match"]
        and checks["vocab_size_match"]
        and checks["block_size"] == 16
        and checks["target_layers"] == [1, 9, 17, 25, 33]
        and checks["num_target_layers_match"]
    )
    return checks
