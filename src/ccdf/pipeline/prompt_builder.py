from __future__ import annotations

from typing import Any


def build_prompt(messages: list[dict[str, Any]], tokenizer: Any | None = None, enable_thinking: bool = False) -> str:
    if tokenizer is not None and hasattr(tokenizer, "apply_chat_template"):
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=enable_thinking,
        )
    return "\n".join(message.get("content", "") for message in messages)