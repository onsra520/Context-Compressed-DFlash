"""Locked local model registry."""

from __future__ import annotations

from pathlib import Path

TARGET_MODEL_ID = "unsloth/Qwen3-4B-bnb-4bit"
TARGET_REVISION = "cad0bedfdd862093a12af478cb974ab2addd0e0a"
TARGET_PATH = Path("models/target/unsloth--Qwen3-4B-bnb-4bit")

DRAFTER_MODEL_ID = "z-lab/Qwen3-4B-DFlash-b16"
DRAFTER_REVISION = "b74e3a329c4d963783143b1e970d95b002be72bd"
DRAFTER_PATH = Path("models/drafter/z-lab--Qwen3-4B-DFlash-b16")


def model_lock() -> dict[str, dict[str, str]]:
    return {
        "target": {
            "model_id": TARGET_MODEL_ID,
            "revision": TARGET_REVISION,
            "path": str(TARGET_PATH),
            "quantization": "bitsandbytes-nf4-bfloat16",
        },
        "drafter": {
            "model_id": DRAFTER_MODEL_ID,
            "revision": DRAFTER_REVISION,
            "path": str(DRAFTER_PATH),
            "block_size": "16",
        },
    }
