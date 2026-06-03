from __future__ import annotations

__all__ = [
    "DFlashDraftModel",
    "Qwen3DFlashAttention",
    "Qwen3DFlashDecoderLayer",
    "apply_rotary_pos_emb",
    "build_target_layer_ids",
    "dflash_generate",
    "extract_context_feature",
    "load_all",
    "load_draft",
    "load_target",
    "load_tokenizer",
    "sample",
    "spec_generate",
]


def __getattr__(name: str):
    if name == "DFlashDraftModel":
        from .model import DFlashDraftModel

        return DFlashDraftModel
    if name == "Qwen3DFlashDecoderLayer":
        from .model import Qwen3DFlashDecoderLayer

        return Qwen3DFlashDecoderLayer
    if name == "Qwen3DFlashAttention":
        from .attention import Qwen3DFlashAttention

        return Qwen3DFlashAttention
    if name == "apply_rotary_pos_emb":
        from .attention import apply_rotary_pos_emb

        return apply_rotary_pos_emb
    if name in {"build_target_layer_ids", "extract_context_feature", "sample"}:
        from .utils import build_target_layer_ids, extract_context_feature, sample

        return {
            "build_target_layer_ids": build_target_layer_ids,
            "extract_context_feature": extract_context_feature,
            "sample": sample,
        }[name]
    if name in {"dflash_generate", "spec_generate"}:
        from .generate import dflash_generate, spec_generate

        return {"dflash_generate": dflash_generate, "spec_generate": spec_generate}[name]
    if name in {"load_target", "load_draft", "load_tokenizer", "load_all"}:
        from .loader import load_all, load_draft, load_target, load_tokenizer

        return {
            "load_target": load_target,
            "load_draft": load_draft,
            "load_tokenizer": load_tokenizer,
            "load_all": load_all,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
