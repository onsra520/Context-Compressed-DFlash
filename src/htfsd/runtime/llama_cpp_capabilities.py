"""Phase 3.12 — llama-cpp-python backend capability status.

This module classifies the available llama-cpp-python API surface for
token-level verification without requiring a loaded model.

Capability classification:
    supported           – API present and confirmed usable from source/version inspection.
    partially_supported – API present but requires specific load flags or has caveats.
    unknown             – Presence uncertain or requires runtime probing with a real model.
    blocked             – API absent or incompatible with the current wrapper design.

The classification is based on inspection of:
    llama_cpp.Llama source in .venv/lib/python3.12/site-packages/llama_cpp/llama.py
    llama-cpp-python version 0.3.23

Do not overclaim. If a capability requires a loaded model, model path, or GPU to
confirm, mark it "unknown" until a real probe confirms it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CapabilityStatus = Literal["supported", "partially_supported", "unknown", "blocked"]


@dataclass(frozen=True)
class LlamaCppCapabilityStatus:
    """Classification of llama-cpp-python API surface for token-level verification.

    Based on static inspection of llama-cpp-python 0.3.23.

    tokenizer_access:
        llama_cpp.Llama.tokenize(text: bytes, add_bos: bool, special: bool) -> list[int]
        Status: supported — method present in source, accepts bytes.

    decode_access:
        llama_cpp.Llama.detokenize(tokens: list[int], prev_tokens, special) -> bytes
        Status: supported — method present in source, returns bytes.
        Note: returns bytes, not str. Callers must .decode("utf-8").

    logits_access:
        self.scores: np.ndarray shape (n_ctx if logits_all else n_batch, n_vocab)
        Status: partially_supported — only populated when logits_all=True at load time.
        With logits_all=False (current LlamaCppBackend default), scores are not saved
        after eval() completes.  Extending the backend to pass logits_all=True would
        enable greedy argmax from self.scores[-1].

    greedy_token_via_sample:
        llama_cpp.Llama.sample(temp=0.0, ...) -> int
        Status: supported — sample() with temp=0.0 returns the greedy (argmax) token.
        This avoids the need to access raw logits directly.

    eval_tokens:
        llama_cpp.Llama.eval(tokens: Sequence[int]) -> None
        Status: supported — method present, updates n_tokens and KV cache.

    one_token_step:
        Calling eval([token]) + sample(temp=0.0) per position.
        Status: partially_supported — eval() and sample() exist, but the current
        LlamaCppBackend wrapper does not expose them.  A thin extension is needed.

    context_reset:
        llama_cpp.Llama.reset() -> None  (sets n_tokens = 0)
        Status: supported — reset() present in source.

    token_eos:
        llama_cpp.Llama.token_eos() -> int
        Status: supported — present in source.

    token_bos:
        llama_cpp.Llama.token_bos() -> int
        Status: supported — present in source.

    n_vocab:
        llama_cpp.Llama.n_vocab() -> int
        Status: supported — present in source.

    wrapper_extension_required:
        The current LlamaCppBackend only exposes generate_text / generate_chat.
        Token-level access requires a thin extension to expose:
            tokenize, detokenize, eval, sample, reset, token_eos, n_tokens.
        This extension must not break existing generate_text / generate_chat interfaces.
    """

    tokenizer_access: CapabilityStatus = "supported"
    decode_access: CapabilityStatus = "supported"
    logits_access: CapabilityStatus = "partially_supported"
    greedy_token_via_sample: CapabilityStatus = "supported"
    eval_tokens: CapabilityStatus = "supported"
    one_token_step: CapabilityStatus = "partially_supported"
    context_reset: CapabilityStatus = "supported"
    token_eos: CapabilityStatus = "supported"
    token_bos: CapabilityStatus = "supported"
    n_vocab: CapabilityStatus = "supported"
    wrapper_extension_required: CapabilityStatus = "partially_supported"

    llama_cpp_python_version: str = "0.3.23"
    inspection_source: str = "static_source_inspection"

    notes: dict[str, str] = field(default_factory=lambda: {
        "logits_access": (
            "Requires logits_all=True at Llama() construction time. "
            "Current LlamaCppBackend passes logits_all=False (default). "
            "Alternative: use sample(temp=0.0) for greedy token without logits."
        ),
        "one_token_step": (
            "eval() and sample() are both present. "
            "Requires wrapper extension to expose them. "
            "Current LlamaCppBackend does not expose eval() or sample()."
        ),
        "wrapper_extension_required": (
            "Phase 3.12 implements a thin VerifierTokenAccess wrapper to expose "
            "tokenize, detokenize, eval, sample, reset, and token_eos "
            "without modifying the existing LlamaCppBackend interface."
        ),
        "greedy_token_via_sample": (
            "sample(temp=0.0) is the preferred greedy approach for Phase 3.12. "
            "It avoids requiring logits_all=True and works with the existing model load."
        ),
    })


# ---------------------------------------------------------------------------
# Runtime probe (optional, requires a loaded Llama model)
# ---------------------------------------------------------------------------


def probe_llama_capabilities(llama_model: object) -> dict[str, str]:
    """Probe a loaded Llama model instance for token-level verification capabilities.

    This function is OPTIONAL and requires a real loaded llama_cpp.Llama instance.
    It is safe to call, but cannot be tested without a model path.
    Use the static LlamaCppCapabilityStatus for unit tests.

    Returns:
        dict mapping capability name to "supported" | "blocked" | "error:<msg>"
    """
    results: dict[str, str] = {}

    # tokenize
    try:
        ids = llama_model.tokenize(b"hello", add_bos=False, special=False)  # type: ignore[attr-defined]
        results["tokenizer_access"] = "supported" if isinstance(ids, list) else "blocked"
    except Exception as exc:
        results["tokenizer_access"] = f"error:{exc}"

    # detokenize
    try:
        text = llama_model.detokenize([1, 2], special=False)  # type: ignore[attr-defined]
        results["decode_access"] = "supported" if isinstance(text, bytes) else "blocked"
    except Exception as exc:
        results["decode_access"] = f"error:{exc}"

    # n_vocab
    try:
        n = llama_model.n_vocab()  # type: ignore[attr-defined]
        results["n_vocab"] = "supported" if isinstance(n, int) else "blocked"
    except Exception as exc:
        results["n_vocab"] = f"error:{exc}"

    # token_eos
    try:
        eos = llama_model.token_eos()  # type: ignore[attr-defined]
        results["token_eos"] = "supported" if isinstance(eos, int) else "blocked"
    except Exception as exc:
        results["token_eos"] = f"error:{exc}"

    # reset
    try:
        llama_model.reset()  # type: ignore[attr-defined]
        results["context_reset"] = "supported"
    except Exception as exc:
        results["context_reset"] = f"error:{exc}"

    # eval + sample
    try:
        ids = llama_model.tokenize(b"hello", add_bos=True, special=False)  # type: ignore[attr-defined]
        llama_model.eval(ids)  # type: ignore[attr-defined]
        token = llama_model.sample(temp=0.0)  # type: ignore[attr-defined]
        results["eval_tokens"] = "supported"
        results["greedy_token_via_sample"] = "supported" if isinstance(token, int) else "blocked"
        results["one_token_step"] = "supported"
    except Exception as exc:
        results["eval_tokens"] = f"error:{exc}"
        results["greedy_token_via_sample"] = f"error:{exc}"
        results["one_token_step"] = f"error:{exc}"

    return results


# ---------------------------------------------------------------------------
# Module-level default status (static, no model required)
# ---------------------------------------------------------------------------

DEFAULT_CAPABILITY_STATUS = LlamaCppCapabilityStatus()
