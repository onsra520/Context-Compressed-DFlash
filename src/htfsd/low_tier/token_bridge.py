"""Phase 3.12 — Token bridge: candidate suffix derivation for D-Flash verification.

Design principle:
    Gemma verifies candidate Gemma tokens derived from Qwen draft text.

This module provides the candidate tokenization pipeline:
    1. Tokenize context_text alone.
    2. Tokenize (context_text + candidate_text) together.
    3. Derive candidate_verifier_token_ids as the suffix.

Combined tokenization is required because SentencePiece tokenizers (used by both
Qwen and Gemma) are boundary-sensitive: tokenizing a candidate in isolation may
produce different ids than tokenizing it as a continuation of the context.

The verifier tokenizer protocol is kept abstract — callers supply a callable that
accepts bytes and returns list[int].  This lets the module be unit-tested with fake
tokenizers and used with llama-cpp-python's Llama.tokenize in production.

Naming:
    candidate_verifier_token_ids : Gemma-side token ids derived from drafter text.
    context_verifier_token_ids   : Gemma-side context token ids.

Do not call these:
    qwen_token_ids, draft_token_ids, accepted_blocks, acceptance_count.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


# ---------------------------------------------------------------------------
# Tokenizer protocol
# ---------------------------------------------------------------------------


class VerifierTokenizer(Protocol):
    """Minimal protocol for the verifier-side tokenizer.

    Matches the interface of llama_cpp.Llama.tokenize (bytes -> list[int]).
    """

    def __call__(
        self,
        text: bytes,
        add_bos: bool = False,
        special: bool = False,
    ) -> list[int]:
        ...


# ---------------------------------------------------------------------------
# Suffix derivation result
# ---------------------------------------------------------------------------


BRIDGE_STATUS_OK = "ok"
BRIDGE_STATUS_EMPTY_CANDIDATE = "empty_candidate"
BRIDGE_STATUS_BOUNDARY_MISMATCH = "boundary_mismatch"
BRIDGE_STATUS_TOKENIZER_ERROR = "tokenizer_error"
BRIDGE_STATUS_BLOCKED = "blocked"

REJECTION_REASON_EMPTY_CANDIDATE = "empty_candidate"
REJECTION_REASON_BOUNDARY_MISMATCH = "tokenization_boundary_mismatch"
REJECTION_REASON_TOKENIZER_ERROR = "tokenizer_error"


@dataclass(frozen=True)
class CandidateSuffixResult:
    """Result of deriving candidate_verifier_token_ids from context + candidate text.

    bridge_status:
        "ok"                          – suffix derivation succeeded.
        "empty_candidate"             – candidate_text is empty or whitespace-only.
        "boundary_mismatch"           – combined tokenization prefix does not match
                                        context tokenization; suffix is unreliable.
        "tokenizer_error"             – tokenizer raised an exception.
        "blocked"                     – tokenizer not available.

    candidate_verifier_token_ids:
        Derived suffix token ids. Empty list on failure.

    context_verifier_token_ids:
        Context token ids used for the derivation.
    """

    bridge_status: str
    candidate_verifier_token_ids: list[int]
    context_verifier_token_ids: list[int]
    combined_token_ids: list[int]
    candidate_text_used: str
    rejection_reason: str | None

    @property
    def ok(self) -> bool:
        return self.bridge_status == BRIDGE_STATUS_OK

    @property
    def candidate_verifier_token_count(self) -> int:
        return len(self.candidate_verifier_token_ids)


# ---------------------------------------------------------------------------
# Suffix derivation function
# ---------------------------------------------------------------------------


def derive_candidate_suffix(
    context_text: str,
    candidate_text: str,
    tokenizer: VerifierTokenizer,
    *,
    add_bos: bool = False,
    strip_candidate: bool = False,
) -> CandidateSuffixResult:
    """Derive candidate_verifier_token_ids from context + candidate text.

    Algorithm:
        context_ids  = tokenizer(context_text)
        combined_ids = tokenizer(context_text + candidate_text)
        candidate_verifier_token_ids = combined_ids[len(context_ids):]

    The suffix is verified by checking that the combined prefix matches the
    context_ids exactly. If it does not match (boundary mismatch), the result
    status is "boundary_mismatch" and the suffix is unreliable.

    Args:
        context_text:     Full context accumulated so far.
        candidate_text:   Raw drafter output for this cycle (post-bridge normalization).
        tokenizer:        Verifier-side tokenizer callable.
        add_bos:          Whether to add BOS token (default False for suffix derivation).
        strip_candidate:  If True, strip leading/trailing whitespace from candidate_text.

    Returns:
        CandidateSuffixResult with bridge_status and candidate_verifier_token_ids.
    """
    if strip_candidate:
        candidate_text = candidate_text.strip()

    # ---- empty candidate check ----
    if not candidate_text:
        return CandidateSuffixResult(
            bridge_status=BRIDGE_STATUS_EMPTY_CANDIDATE,
            candidate_verifier_token_ids=[],
            context_verifier_token_ids=[],
            combined_token_ids=[],
            candidate_text_used=candidate_text,
            rejection_reason=REJECTION_REASON_EMPTY_CANDIDATE,
        )

    # ---- tokenize context alone ----
    try:
        context_ids = tokenizer(context_text.encode("utf-8"), add_bos=add_bos, special=False)
    except Exception as exc:
        return CandidateSuffixResult(
            bridge_status=BRIDGE_STATUS_TOKENIZER_ERROR,
            candidate_verifier_token_ids=[],
            context_verifier_token_ids=[],
            combined_token_ids=[],
            candidate_text_used=candidate_text,
            rejection_reason=f"{REJECTION_REASON_TOKENIZER_ERROR}: {exc}",
        )

    # ---- tokenize context + candidate together ----
    try:
        combined_ids = tokenizer(
            (context_text + candidate_text).encode("utf-8"),
            add_bos=add_bos,
            special=False,
        )
    except Exception as exc:
        return CandidateSuffixResult(
            bridge_status=BRIDGE_STATUS_TOKENIZER_ERROR,
            candidate_verifier_token_ids=[],
            context_verifier_token_ids=list(context_ids),
            combined_token_ids=[],
            candidate_text_used=candidate_text,
            rejection_reason=f"{REJECTION_REASON_TOKENIZER_ERROR}: {exc}",
        )

    # ---- boundary mismatch guard ----
    # The combined tokenization must start with the same ids as the context tokenization.
    # If not, the suffix derivation is unreliable.
    n_ctx = len(context_ids)
    if len(combined_ids) < n_ctx:
        return CandidateSuffixResult(
            bridge_status=BRIDGE_STATUS_BOUNDARY_MISMATCH,
            candidate_verifier_token_ids=[],
            context_verifier_token_ids=list(context_ids),
            combined_token_ids=list(combined_ids),
            candidate_text_used=candidate_text,
            rejection_reason=REJECTION_REASON_BOUNDARY_MISMATCH,
        )

    prefix_match = combined_ids[:n_ctx] == context_ids
    if not prefix_match:
        return CandidateSuffixResult(
            bridge_status=BRIDGE_STATUS_BOUNDARY_MISMATCH,
            candidate_verifier_token_ids=[],
            context_verifier_token_ids=list(context_ids),
            combined_token_ids=list(combined_ids),
            candidate_text_used=candidate_text,
            rejection_reason=REJECTION_REASON_BOUNDARY_MISMATCH,
        )

    # ---- derive candidate suffix ----
    candidate_ids = combined_ids[n_ctx:]

    if not candidate_ids:
        return CandidateSuffixResult(
            bridge_status=BRIDGE_STATUS_EMPTY_CANDIDATE,
            candidate_verifier_token_ids=[],
            context_verifier_token_ids=list(context_ids),
            combined_token_ids=list(combined_ids),
            candidate_text_used=candidate_text,
            rejection_reason=REJECTION_REASON_EMPTY_CANDIDATE,
        )

    return CandidateSuffixResult(
        bridge_status=BRIDGE_STATUS_OK,
        candidate_verifier_token_ids=list(candidate_ids),
        context_verifier_token_ids=list(context_ids),
        combined_token_ids=list(combined_ids),
        candidate_text_used=candidate_text,
        rejection_reason=None,
    )


# ---------------------------------------------------------------------------
# Fake tokenizer for testing (no model dependency)
# ---------------------------------------------------------------------------


def make_word_tokenizer(
    vocab: dict[str, int] | None = None,
) -> Callable[[bytes, bool, bool], list[int]]:
    """Build a simple deterministic word-split tokenizer for unit tests.

    Maps each space-separated word to a fixed id. Unknown words get id 999.
    Useful for testing suffix derivation logic without a real model.

    Example:
        tok = make_word_tokenizer({"hello": 1, "world": 2})
        tok(b"hello world", add_bos=False, special=False)  # -> [1, 2]
    """
    if vocab is None:
        # Generate a stable mapping for arbitrary words
        vocab = {}

    def _tokenize(text: bytes, add_bos: bool = False, special: bool = False) -> list[int]:
        words = text.decode("utf-8").split(" ")
        ids: list[int] = []
        for w in words:
            if not w:
                continue
            if w not in vocab:
                vocab[w] = hash(w) % 900 + 100  # stable pseudo-id in range 100-999
            ids.append(vocab[w])
        return ids

    return _tokenize
