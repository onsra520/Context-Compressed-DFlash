from __future__ import annotations


def build_dflash_prompt(context: str, *, max_tokens: int) -> str:
    return (
        "Return only one compact JSON object. "
        "Do not use Markdown fences. Do not explain. "
        'The object must contain "draft_text" and may contain "confidence" and "max_tokens". '
        f"Use at most {max_tokens} continuation tokens. "
        "Context:\n"
        f"{context}\n"
        'JSON shape: {"draft_text":"...","confidence":0.7,"max_tokens":'
        f"{max_tokens}"
        "}"
    )
