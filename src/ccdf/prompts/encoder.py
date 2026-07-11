"""Exact Qwen chat-template encoding used by every production condition."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ccdf.datasets.hashing import hash_json, hash_text
from ccdf.prompts.renderer import build_messages, render_prompt
from ccdf.prompts.schemas import EncodedPrompt, PromptParts


def _flatten_input_ids(value: Any):
    import torch

    if isinstance(value, dict):
        value = value["input_ids"]
    if hasattr(value, "input_ids"):
        value = value.input_ids
    if isinstance(value, list):
        value = torch.tensor([value], dtype=torch.long)
    if value.ndim == 1:
        value = value.unsqueeze(0)
    return value


def _apply_chat_template(tokenizer, messages: list[dict[str, str]], enable_thinking: bool):
    """Call the installed tokenizer without assuming one Transformers minor API."""

    kwargs = {
        "tokenize": True,
        "add_generation_prompt": True,
        "return_tensors": "pt",
    }
    thinking_applied = False
    try:
        encoded = tokenizer.apply_chat_template(
            messages,
            enable_thinking=enable_thinking,
            **kwargs,
        )
        thinking_applied = True
    except TypeError:
        try:
            encoded = tokenizer.apply_chat_template(
                messages,
                chat_template_kwargs={"enable_thinking": enable_thinking},
                **kwargs,
            )
            thinking_applied = True
        except TypeError:
            encoded = tokenizer.apply_chat_template(messages, **kwargs)
    return _flatten_input_ids(encoded), thinking_applied


def encode_prompt(
    tokenizer,
    *,
    parts: PromptParts,
    dataset: str,
    enable_thinking: bool,
    device,
) -> EncodedPrompt:
    messages = build_messages(parts, dataset)
    rendered = render_prompt(parts, dataset)
    chat_template_used = callable(getattr(tokenizer, "apply_chat_template", None))
    if chat_template_used:
        input_ids, thinking_applied = _apply_chat_template(tokenizer, messages, enable_thinking)
    else:
        input_ids = tokenizer(rendered, return_tensors="pt").input_ids
        thinking_applied = False
    input_ids = input_ids.to(device)
    ids = tuple(int(item) for item in input_ids[0].detach().cpu().tolist())
    structured = {
        "dataset": dataset,
        "parts": asdict(parts),
        "messages": messages,
        "add_generation_prompt": True,
        "enable_thinking": enable_thinking,
    }
    return EncodedPrompt(
        dataset=dataset,
        parts=parts,
        messages=tuple(messages),
        rendered_text=rendered,
        input_ids=input_ids,
        input_ids_list=ids,
        structured_hash=hash_json(structured),
        rendered_hash=hash_text(rendered),
        input_ids_hash=hash_json(list(ids)),
        chat_template_used=chat_template_used,
        enable_thinking_applied=thinking_applied,
    )
