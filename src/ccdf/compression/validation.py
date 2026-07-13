"""Prompt and token-scope validation."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from ccdf.compression.schemas import CompressionResult
from ccdf.prompts.encoder import encode_prompt
from ccdf.prompts.renderer import render_prompt
from ccdf.prompts.schemas import PromptParts


def prompt_invariants(
    original: PromptParts, compressed_context: str, *, dataset: str = "qmsum"
) -> dict[str, object]:
    compressed = PromptParts(
        context=compressed_context,
        question=original.question,
        instruction=original.instruction,
        system=original.system,
    )
    original_prompt = render_prompt(original, dataset)
    final_prompt = render_prompt(compressed, dataset)
    if dataset == "gsm8k":
        context_marker = "Problem:\n"
    elif dataset == "qmsum":
        context_marker = "Meeting transcript:\n"
    else:
        context_marker = "Context:\n" if original.context or compressed_context else ""

    return {
        "question_occurrence": final_prompt.count(original.question),
        "instruction_occurrence": final_prompt.count(original.instruction),
        "context_marker_preserved": context_marker in final_prompt if context_marker else True,
        "meeting_marker_preserved": ("Meeting transcript:\n" in final_prompt) if dataset == "qmsum" else True,
        "question_marker_preserved": ("\n\nQuestion:\n" in final_prompt) if dataset == "qmsum" else True,
        "only_context_changed": final_prompt.replace(compressed_context, original.context, 1)
        == original_prompt
        if original.context or compressed_context
        else final_prompt == original_prompt,
        "final_prompt": final_prompt,
    }


def validate_prompt_invariants(
    original: PromptParts, compressed_context: str, *, dataset: str = "qmsum"
) -> None:
    audit = prompt_invariants(original, compressed_context, dataset=dataset)
    if audit["question_occurrence"] != 1:
        raise ValueError("question occurrence must equal 1")
    if audit["instruction_occurrence"] != 1:
        raise ValueError("instruction occurrence must equal 1")
    if not audit["context_marker_preserved"] or not audit["question_marker_preserved"]:
        raise ValueError("prompt markers not preserved")
    if not audit["only_context_changed"]:
        raise ValueError("prompt reconstruction changed more than context")


def token_scope_audit(
    original: PromptParts,
    result: CompressionResult,
    *,
    target_tokenizer_path: Path | None = None,
    dataset: str = "qmsum",
    enable_thinking: bool = False,
) -> dict[str, object]:
    """Compatibility helper using exact chat-template IDs.

    Production RuntimeEngine already has the tokenizer loaded and computes this
    scope without a second model load.
    """

    final_parts = PromptParts(
        context=result.compressed_context,
        question=original.question,
        instruction=original.instruction,
        system=original.system,
    )
    if target_tokenizer_path is None:
        # Legacy/source-only compatibility. Canonical runtime never uses this
        # fallback; RuntimeEngine counts exact chat-template IDs with its
        # already-loaded target tokenizer.
        import re

        pre_text = render_prompt(original, dataset)
        final_text = render_prompt(final_parts, dataset)
        pre_full = len(re.findall(r"\w+|[^\w\s]", pre_text))
        final_full = len(re.findall(r"\w+|[^\w\s]", final_text))
        tokenizer_id = "legacy-rendered-text-fallback"
        exact_scope = False
    else:
        from transformers import AutoTokenizer

        target_tokenizer = AutoTokenizer.from_pretrained(
            target_tokenizer_path, local_files_only=True, trust_remote_code=True
        )
        pre = encode_prompt(
            target_tokenizer,
            parts=original,
            dataset=dataset,
            enable_thinking=enable_thinking,
            device="cpu",
        )
        final = encode_prompt(
            target_tokenizer,
            parts=final_parts,
            dataset=dataset,
            enable_thinking=enable_thinking,
            device="cpu",
        )
        pre_full = len(pre.input_ids_list)
        final_full = len(final.input_ids_list)
        tokenizer_id = str(target_tokenizer_path)
        exact_scope = True

    return {
        "compression_result": asdict(result),
        "segment_tokenizer_id": result.segment_tokenizer_id,
        "target_tokenizer_id": tokenizer_id,
        "precompression_target_prompt_tokens": pre_full,
        "final_target_prompt_tokens": final_full,
        "full_prompt_retained_ratio": final_full / pre_full if pre_full else 1.0,
        "full_prompt_reduction_pct": (1.0 - (final_full / pre_full)) * 100 if pre_full else 0.0,
        "tokenizer_scopes_separate": result.segment_tokenizer_id != tokenizer_id,
        "exact_chat_template_scope": exact_scope,
    }
