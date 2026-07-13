"""
Non-canonical frontend demo runtime adapter.

Uses real RuntimeEngine + RuntimeRequest. Never calls `ccdf run --prompt`.
Implements a generic demo policy that is explicitly noncanonical.

Key behaviours:
- Uses qmsum config as the base, then overrides dataset/canonical/policy.
- question-only: context is empty → compressor bypass is triggered inside
  _compress() (PassthroughCompressor, bypass_reason="empty_context").
  demo_bypass_compressor_load=True prevents the LLMLingua model from being
  loaded at engine init, which would waste VRAM for a no-op.
- context + question CPU:  cc-dflash-r2  (CPU compressor)
- context + question GPU:  cc-dflash-r2-gpu (CUDA compressor; verified)
"""
from __future__ import annotations

from typing import Any

from ccdf.config import resolve_config
from ccdf.prompts.schemas import PromptParts
from ccdf.runtime import RuntimeRequest, execute_request

# Generic demo instruction that does not echo the prompt policy text.
_DEMO_INSTRUCTION_CONTEXT = (
    "Answer the question using only the provided context. "
    "Be concise and do not repeat the question or instructions."
)
_DEMO_INSTRUCTION_NO_CONTEXT = (
    "Answer the user's question directly and concisely. "
    "Do not repeat the question or instructions."
)


def run_demo_condition(
    context: str,
    question: str,
    condition_id: str,
) -> dict[str, Any]:
    """Execute a single condition and return the raw engine result dict.

    The caller (metric_normalizer) is responsible for extracting display-ready
    metrics.  This function must not invent or mock any values.
    """
    has_context = bool(context.strip())
    instruction = (
        _DEMO_INSTRUCTION_CONTEXT if has_context else _DEMO_INSTRUCTION_NO_CONTEXT
    )

    # Resolve from qmsum so all model paths, compression config, and generation
    # config are correct.  execution_mode="smoke" limits max_new_tokens to a
    # smaller value appropriate for interactive demo use.
    resolved = resolve_config(
        dataset="qmsum",
        subset="n10",
        condition_id=condition_id,
        execution_mode="smoke",
    )

    # --- Noncanonical overrides ---
    resolved.data["dataset"] = "frontend_demo"
    resolved.data["canonical"] = False
    resolved.data["prompt_policy"]["text"] = instruction

    # For question-only inputs, prevent the compressor from being loaded at
    # engine init.  _compress() still runs but uses PassthroughCompressor
    # (bypass_reason="empty_context") so no compressor is needed.
    if not has_context:
        resolved.data["demo_bypass_compressor_load"] = True

    parts = PromptParts(
        context=context,
        question=question,
        instruction=instruction,
        system=resolved.data["prompts"].get("system"),
    )

    request = RuntimeRequest(
        resolved=resolved,
        prompt=None,
        prompt_parts=parts,
        measurement_mode="profiling",
    )

    result = execute_request(request)
    # Tag with condition_id so the normalizer can find it.
    result["condition"] = condition_id
    return result
