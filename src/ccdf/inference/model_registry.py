"""Locked model identities.

Paths are resolved by :mod:`ccdf.paths`; this module is identity-only and must
not select production filesystem locations.
"""

from __future__ import annotations

TARGET_MODEL_ID = "unsloth/Qwen3-4B-bnb-4bit"
TARGET_REVISION = "cad0bedfdd862093a12af478cb974ab2addd0e0a"
BASELINE_MODEL_ID = "unsloth/Qwen3-8B-bnb-4bit"
BASELINE_REVISION = "1deaf68f694c40dbce295da300851729d759b21a"
DRAFTER_MODEL_ID = "z-lab/Qwen3-4B-DFlash-b16"
DRAFTER_REVISION = "b74e3a329c4d963783143b1e970d95b002be72bd"

# Backward-compatible logical paths. Production resolves these through
# ``configs/reconstruction.yml`` and never imports them as filesystem paths.
TARGET_PATH = "@shared/models/target/unsloth--Qwen3-4B-bnb-4bit"
BASELINE_PATH = "@shared/models/target/unsloth--Qwen3-8B-bnb-4bit"
DRAFTER_PATH = "@shared/models/drafter/z-lab--Qwen3-4B-DFlash-b16"


def model_lock() -> dict[str, dict[str, str]]:
    return {
        "baseline": {
            "model_id": BASELINE_MODEL_ID,
            "revision": BASELINE_REVISION,
            "path": BASELINE_PATH,
            "quantization": "bitsandbytes-nf4-bfloat16",
        },
        "target": {
            "model_id": TARGET_MODEL_ID,
            "revision": TARGET_REVISION,
            "path": TARGET_PATH,
            "quantization": "bitsandbytes-nf4-bfloat16",
        },
        "drafter": {
            "model_id": DRAFTER_MODEL_ID,
            "revision": DRAFTER_REVISION,
            "path": DRAFTER_PATH,
            "block_size": "16",
        },
    }
