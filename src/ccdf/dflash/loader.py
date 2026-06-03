from __future__ import annotations

import re
import logging

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .model import DFlashDraftModel


logger = logging.getLogger(__name__)

_TRANSFORMERS_SUPPORTED_PATTERN = re.compile(
    r"qwen3(?!\.5)[\w-]*|llama.*3\.1.*8b.*instruct", re.IGNORECASE
)


def _check_transformers_model(model_name: str) -> None:
    if not _TRANSFORMERS_SUPPORTED_PATTERN.search(model_name):
        raise ValueError(
            f"Transformers backend does not support '{model_name}'. "
            f"Only Qwen3 series and LLaMA-3.1-8B-Instruct are supported. "
            f"Use --backend sglang or --backend vllm for other models."
        )


def _get_transformers_attn_impl() -> str:
    try:
        import flash_attn  # noqa: F401

        return "flash_attention_2"
    except ImportError:
        logger.warning(
            "flash_attn not installed. Falling back to torch.sdpa. Speedup will be lower. "
            "For optimal speedup in Transformers backend, please install: "
            "pip install flash-attn --no-build-isolation"
        )
        return "sdpa"


def load_target(
    model_id: str,
    *,
    device: torch.device | str | None = None,
    attn_implementation: str | None = None,
    dtype: torch.dtype = torch.bfloat16,
    **kwargs,
):
    _check_transformers_model(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        attn_implementation=attn_implementation or _get_transformers_attn_impl(),
        dtype=dtype,
        **kwargs,
    )
    if device is not None:
        model = model.to(device)
    return model.eval()


def load_draft(
    model_id: str,
    *,
    device: torch.device | str | None = None,
    attn_implementation: str | None = None,
    dtype: torch.dtype = torch.bfloat16,
    **kwargs,
):
    model = DFlashDraftModel.from_pretrained(
        model_id,
        attn_implementation=attn_implementation or _get_transformers_attn_impl(),
        dtype=dtype,
        **kwargs,
    )
    if device is not None:
        model = model.to(device)
    return model.eval()


def load_tokenizer(model_id: str, **kwargs):
    return AutoTokenizer.from_pretrained(model_id, **kwargs)


def load_all(
    target_id: str,
    draft_id: str,
    *,
    tokenizer_id: str | None = None,
    device: torch.device | str | None = None,
    attn_implementation: str | None = None,
    dtype: torch.dtype = torch.bfloat16,
):
    attn_impl = attn_implementation or _get_transformers_attn_impl()
    target = load_target(
        target_id,
        device=device,
        attn_implementation=attn_impl,
        dtype=dtype,
    )
    draft = load_draft(
        draft_id,
        device=device,
        attn_implementation=attn_impl,
        dtype=dtype,
    )
    tokenizer = load_tokenizer(tokenizer_id or target_id)
    return target, draft, tokenizer
