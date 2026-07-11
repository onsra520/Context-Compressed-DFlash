"""Prompt and token-scope validation."""

from __future__ import annotations

from dataclasses import asdict

from transformers import AutoTokenizer

from ccdf.compression.schemas import CompressionResult
from ccdf.inference.model_registry import TARGET_PATH
from ccdf.prompts.renderer import render_prompt
from ccdf.prompts.schemas import PromptParts


def prompt_invariants(original: PromptParts, compressed_context: str) -> dict[str, object]:
    compressed = PromptParts(
        context=compressed_context,
        question=original.question,
        instruction=original.instruction,
        system=original.system,
    )
    original_prompt = render_prompt(original)
    final_prompt = render_prompt(compressed)
    return {
        "question_occurrence": final_prompt.count(original.question),
        "instruction_occurrence": final_prompt.count(original.instruction),
        "meeting_marker_preserved": "Meeting transcript:\n" in final_prompt,
        "question_marker_preserved": "\n\nQuestion:\n" in final_prompt,
        "only_context_changed": final_prompt.replace(compressed_context, original.context, 1)
        == original_prompt,
        "final_prompt": final_prompt,
    }


def validate_prompt_invariants(original: PromptParts, compressed_context: str) -> None:
    audit = prompt_invariants(original, compressed_context)
    if audit["question_occurrence"] != 1:
        raise ValueError("question occurrence must equal 1")
    if audit["instruction_occurrence"] != 1:
        raise ValueError("instruction occurrence must equal 1")
    if not audit["meeting_marker_preserved"] or not audit["question_marker_preserved"]:
        raise ValueError("prompt markers not preserved")
    if not audit["only_context_changed"]:
        raise ValueError("prompt reconstruction changed more than context")


def token_scope_audit(
    original: PromptParts, result: CompressionResult, *, target_tokenizer_path=TARGET_PATH
) -> dict[str, object]:
    target_tokenizer = AutoTokenizer.from_pretrained(target_tokenizer_path, local_files_only=True)
    final_parts = PromptParts(
        context=result.compressed_context,
        question=original.question,
        instruction=original.instruction,
        system=original.system,
    )
    pre_prompt = render_prompt(original)
    final_prompt = render_prompt(final_parts)
    pre_full = len(target_tokenizer.encode(pre_prompt, add_special_tokens=False))
    final_full = len(target_tokenizer.encode(final_prompt, add_special_tokens=False))
    return {
        "compression_result": asdict(result),
        "segment_tokenizer_id": result.segment_tokenizer_id,
        "target_tokenizer_id": str(target_tokenizer_path),
        "precompression_target_prompt_tokens": pre_full,
        "final_target_prompt_tokens": final_full,
        "full_prompt_retained_ratio": final_full / pre_full if pre_full else 1.0,
        "full_prompt_reduction_pct": (1.0 - (final_full / pre_full)) * 100 if pre_full else 0.0,
        "tokenizer_scopes_separate": result.segment_tokenizer_id != str(target_tokenizer_path),
    }
