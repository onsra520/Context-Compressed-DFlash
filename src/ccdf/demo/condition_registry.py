from __future__ import annotations

CONDITIONS = {
    "baseline_ar": {
        "id": "baseline_ar",
        "display_name": "Baseline-AR",
        "uses_compression": False,
        "uses_dflash": False,
    },
    "dflash_r1": {
        "id": "dflash_r1",
        "display_name": "DFlash-R1",
        "uses_compression": False,
        "uses_dflash": True,
    },
    "cc_dflash_r2": {
        "id": "cc_dflash_r2",
        "display_name": "CC-DFlash-R2 Light GPU",
        "uses_compression": True,
        "uses_dflash": True,
        "keep_rate": 0.5,
    },
}


def get_condition(condition_id: str) -> dict:
    if condition_id not in CONDITIONS:
        raise ValueError(f"Unknown condition: {condition_id}")
    return CONDITIONS[condition_id]


def validate_condition(condition_id: str) -> None:
    if condition_id not in CONDITIONS:
        raise ValueError(f"Unknown condition: {condition_id}")
