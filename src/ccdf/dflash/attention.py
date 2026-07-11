"""Attention contract checks for recovered DFlash drafter."""

from __future__ import annotations


def validate_attention_contract(config) -> dict[str, object]:
    layer_types = list(getattr(config, "layer_types", []))
    return {
        "attention_bias": bool(config.attention_bias),
        "attention_dropout": float(config.attention_dropout),
        "layer_types": layer_types,
        "is_full_attention_only": bool(layer_types) and all(item == "full_attention" for item in layer_types),
        "num_attention_heads": int(config.num_attention_heads),
        "num_key_value_heads": int(config.num_key_value_heads),
    }
