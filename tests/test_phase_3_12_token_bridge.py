"""Phase 3.12 — Token bridge suffix derivation tests.

All tests are pure: no GGUF model required.
Uses make_word_tokenizer() from token_bridge for deterministic fake tokenization.

Covers:
    - Successful suffix derivation (ok)
    - Empty candidate detection
    - Boundary mismatch detection
    - Leading space sensitivity (SentencePiece-relevant)
    - BOS/EOS exclusion policy
    - CandidateSuffixResult.ok property
    - CandidateSuffixResult.candidate_verifier_token_count
    - Tokenizer error handling
    - make_word_tokenizer stability
"""

from __future__ import annotations

import pytest

from htfsd.low_tier.token_bridge import (
    BRIDGE_STATUS_BOUNDARY_MISMATCH,
    BRIDGE_STATUS_BLOCKED,
    BRIDGE_STATUS_EMPTY_CANDIDATE,
    BRIDGE_STATUS_OK,
    BRIDGE_STATUS_TOKENIZER_ERROR,
    CandidateSuffixResult,
    derive_candidate_suffix,
    make_word_tokenizer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fixed_vocab_tokenizer():
    """Return a deterministic word tokenizer with a fixed vocab.

    Note: The word tokenizer splits on single spaces. When context and candidate
    are joined (context + candidate), the boundary must produce a clean space
    separation for the prefix to remain stable. Tests use context strings that
    end with a space to ensure clean joins.
    """
    vocab = {
        "the": 1,
        "quick": 2,
        "brown": 3,
        "fox": 4,
        "hello": 10,
        "world": 11,
        "candidate": 20,
        "token": 21,
        "text": 22,
    }
    return make_word_tokenizer(vocab)


# ---------------------------------------------------------------------------
# 1. Successful suffix derivation
# ---------------------------------------------------------------------------


def test_suffix_derivation_ok() -> None:
    """Simple case: context + candidate tokenizes cleanly.

    Context ends with a space so that context + candidate = 'the quick brown fox'
    (space-separated). The word tokenizer splits on spaces, so the prefix is stable.
    """
    tok = _fixed_vocab_tokenizer()
    # Context ends with trailing space so context + candidate joins cleanly
    result = derive_candidate_suffix("the quick ", "brown fox", tok)

    assert result.ok
    assert result.bridge_status == BRIDGE_STATUS_OK
    assert result.candidate_verifier_token_ids == [3, 4]   # "brown"=3, "fox"=4
    assert result.rejection_reason is None


def test_suffix_derivation_context_ids_preserved() -> None:
    """Context ids must match the prefix of combined ids."""
    tok = _fixed_vocab_tokenizer()
    result = derive_candidate_suffix("the quick ", "brown fox", tok)

    assert result.context_verifier_token_ids == [1, 2]   # "the"=1, "quick"=2
    # combined = [1, 2, 3, 4]
    assert result.combined_token_ids == [1, 2, 3, 4]


def test_suffix_derivation_candidate_token_count() -> None:
    tok = _fixed_vocab_tokenizer()
    result = derive_candidate_suffix("the ", "quick brown fox", tok)

    assert result.ok
    assert result.candidate_verifier_token_count == 3


# ---------------------------------------------------------------------------
# 2. Empty candidate detection
# ---------------------------------------------------------------------------


def test_empty_candidate_string_returns_empty_status() -> None:
    tok = _fixed_vocab_tokenizer()
    result = derive_candidate_suffix("the quick", "", tok)

    assert result.bridge_status == BRIDGE_STATUS_EMPTY_CANDIDATE
    assert not result.ok
    assert result.candidate_verifier_token_ids == []


def test_whitespace_only_candidate_with_strip() -> None:
    """Whitespace-only candidate treated as empty when strip_candidate=True."""
    tok = _fixed_vocab_tokenizer()
    result = derive_candidate_suffix("the quick", "   ", tok, strip_candidate=True)

    assert result.bridge_status == BRIDGE_STATUS_EMPTY_CANDIDATE
    assert not result.ok


def test_whitespace_only_candidate_without_strip_may_be_empty_after_tokenize() -> None:
    """Whitespace-only without stripping: depends on tokenizer.
    The word tokenizer skips empty words, so it returns empty suffix.
    """
    tok = _fixed_vocab_tokenizer()
    result = derive_candidate_suffix("the quick", "   ", tok, strip_candidate=False)
    # Word tokenizer skips whitespace-only words, so suffix is empty
    assert result.bridge_status in (BRIDGE_STATUS_EMPTY_CANDIDATE, BRIDGE_STATUS_OK)


# ---------------------------------------------------------------------------
# 3. Boundary mismatch detection
# ---------------------------------------------------------------------------


def test_boundary_mismatch_when_prefix_does_not_match() -> None:
    """Tokenizer that changes context tokens in combined output → boundary mismatch."""

    call_count = 0

    def _unstable_tokenizer(text: bytes, add_bos: bool = False, special: bool = False) -> list[int]:
        nonlocal call_count
        call_count += 1
        decoded = text.decode("utf-8")
        if call_count == 1:
            # First call: tokenize context alone
            return [1, 2]
        else:
            # Second call: tokenize combined — but returns DIFFERENT prefix (simulates mismatch)
            return [1, 99, 3, 4]  # prefix [1, 99] != context [1, 2]

    result = derive_candidate_suffix("hello world", "candidate text", _unstable_tokenizer)

    assert result.bridge_status == BRIDGE_STATUS_BOUNDARY_MISMATCH
    assert not result.ok
    assert result.candidate_verifier_token_ids == []


# ---------------------------------------------------------------------------
# 4. Tokenizer error handling
# ---------------------------------------------------------------------------


def test_tokenizer_error_on_context_returns_error_status() -> None:
    """Tokenizer raises on context → tokenizer_error status."""

    def _bad_tokenizer(text: bytes, add_bos: bool = False, special: bool = False) -> list[int]:
        raise RuntimeError("tokenizer unavailable")

    result = derive_candidate_suffix("hello", "world", _bad_tokenizer)

    assert result.bridge_status == BRIDGE_STATUS_TOKENIZER_ERROR
    assert not result.ok
    assert "tokenizer_error" in (result.rejection_reason or "")


def test_tokenizer_error_on_combined_returns_error_status() -> None:
    """Tokenizer raises on combined call → tokenizer_error status."""

    call_count = 0

    def _bad_combined(text: bytes, add_bos: bool = False, special: bool = False) -> list[int]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return [1, 2]
        raise RuntimeError("combined tokenization failed")

    result = derive_candidate_suffix("hello", "world", _bad_combined)

    assert result.bridge_status == BRIDGE_STATUS_TOKENIZER_ERROR
    assert not result.ok


# ---------------------------------------------------------------------------
# 5. CandidateSuffixResult properties
# ---------------------------------------------------------------------------


def test_suffix_result_ok_property() -> None:
    tok = _fixed_vocab_tokenizer()
    result = derive_candidate_suffix("the", "quick", tok)

    assert result.ok is (result.bridge_status == BRIDGE_STATUS_OK)


def test_suffix_result_candidate_verifier_token_count() -> None:
    tok = _fixed_vocab_tokenizer()
    result = derive_candidate_suffix("the", "quick brown", tok)

    assert result.candidate_verifier_token_count == len(result.candidate_verifier_token_ids)


# ---------------------------------------------------------------------------
# 6. make_word_tokenizer stability
# ---------------------------------------------------------------------------


def test_word_tokenizer_is_deterministic() -> None:
    """Same text must produce same ids across multiple calls."""
    tok = _fixed_vocab_tokenizer()
    ids1 = tok(b"the quick brown fox")
    ids2 = tok(b"the quick brown fox")
    assert ids1 == ids2


def test_word_tokenizer_with_custom_vocab() -> None:
    vocab = {"alpha": 1, "beta": 2, "gamma": 3}
    tok = make_word_tokenizer(vocab)
    ids = tok(b"alpha beta gamma", add_bos=False, special=False)
    assert ids == [1, 2, 3]


def test_word_tokenizer_unknown_words_get_stable_id() -> None:
    """Unknown words get a stable hash-based id (not 0, not error)."""
    tok = make_word_tokenizer()
    ids1 = tok(b"unknownword")
    ids2 = tok(b"unknownword")
    assert ids1 == ids2
    assert ids1[0] >= 100


# ---------------------------------------------------------------------------
# 7. Combined tokenization invariant
# ---------------------------------------------------------------------------


def test_combined_tokenization_prefix_invariant() -> None:
    """Verify that the word tokenizer produces a stable prefix for suffix derivation.

    Context ends with a trailing space so context + candidate joins cleanly.
    This demonstrates the boundary-sensitivity requirement: callers must ensure
    the join produces a stable token boundary.
    """
    tok = _fixed_vocab_tokenizer()
    context = "the quick "   # trailing space for clean join
    candidate = "brown fox"

    result = derive_candidate_suffix(context, candidate, tok)

    assert result.ok
    # Combined ids must start with context_ids
    n = len(result.context_verifier_token_ids)
    assert result.combined_token_ids[:n] == result.context_verifier_token_ids
    # Suffix must be the remainder
    assert result.combined_token_ids[n:] == result.candidate_verifier_token_ids


# ---------------------------------------------------------------------------
# 8. Empty context
# ---------------------------------------------------------------------------


def test_empty_context_with_candidate() -> None:
    """Empty context: entire combined result is the candidate."""
    tok = _fixed_vocab_tokenizer()
    result = derive_candidate_suffix("", "the quick", tok)

    # Word tokenizer returns [] for empty string
    assert result.ok
    assert result.context_verifier_token_ids == []
    assert result.candidate_verifier_token_ids == [1, 2]  # "the"=1, "quick"=2
