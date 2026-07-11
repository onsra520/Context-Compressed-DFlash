"""DFlash-R1 production wrapper."""

from __future__ import annotations

from ccdf.dflash.generate import generate_dflash
from ccdf.inference.schemas import GenerationConfig, GenerationResult


def generate_dflash_r1(target, drafter, tokenizer, input_ids, config: GenerationConfig) -> GenerationResult:
    return generate_dflash(
        target=target,
        drafter=drafter,
        tokenizer=tokenizer,
        input_ids=input_ids,
        config=config,
    )
