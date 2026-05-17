from __future__ import annotations

from dflash.prompts import build_dflash_prompt
from runtime.vllm_adapter import VllmGenerationAdapter


class QwenDFlashDrafter:  # pylint: disable=too-few-public-methods
    def __init__(self, generation: VllmGenerationAdapter):
        self._generation = generation

    def draft(self, context_text: str, *, max_tokens: int) -> str:
        prompt = build_dflash_prompt(context_text, max_tokens=max_tokens)
        return self._generation.generate_text(
            prompt,
            max_tokens=max_tokens * 8,
            temperature=0.0,
            top_p=1.0,
        )
