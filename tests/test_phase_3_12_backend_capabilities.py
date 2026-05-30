"""Phase 3.12 — Backend capability status tests.

All tests are pure: no GGUF model, no model path, no GPU required.
Tests verify the static capability classification for llama-cpp-python 0.3.23.

Optional/manual tests that require a real model are marked:
    @pytest.mark.skip(reason="requires real GGUF model")

Covers:
    - LlamaCppCapabilityStatus fields and defaults
    - Capability status values are valid literals
    - Version is recorded
    - Notes are present for partially_supported capabilities
    - DEFAULT_CAPABILITY_STATUS is accessible
"""

from __future__ import annotations

import pytest

from htfsd.runtime.llama_cpp_capabilities import (
    DEFAULT_CAPABILITY_STATUS,
    LlamaCppCapabilityStatus,
)

VALID_STATUSES = {"supported", "partially_supported", "unknown", "blocked"}


# ---------------------------------------------------------------------------
# 1. Static capability classification
# ---------------------------------------------------------------------------


def test_capability_status_has_expected_fields() -> None:
    status = LlamaCppCapabilityStatus()
    assert hasattr(status, "tokenizer_access")
    assert hasattr(status, "decode_access")
    assert hasattr(status, "logits_access")
    assert hasattr(status, "greedy_token_via_sample")
    assert hasattr(status, "eval_tokens")
    assert hasattr(status, "one_token_step")
    assert hasattr(status, "context_reset")
    assert hasattr(status, "token_eos")
    assert hasattr(status, "token_bos")
    assert hasattr(status, "n_vocab")
    assert hasattr(status, "wrapper_extension_required")


def test_capability_status_values_are_valid() -> None:
    status = LlamaCppCapabilityStatus()
    for field_name in (
        "tokenizer_access",
        "decode_access",
        "logits_access",
        "greedy_token_via_sample",
        "eval_tokens",
        "one_token_step",
        "context_reset",
        "token_eos",
        "token_bos",
        "n_vocab",
        "wrapper_extension_required",
    ):
        value = getattr(status, field_name)
        assert value in VALID_STATUSES, (
            f"Field {field_name!r} has invalid status {value!r}"
        )


def test_tokenizer_access_is_supported() -> None:
    """llama_cpp.Llama.tokenize is confirmed present in llama-cpp-python 0.3.23."""
    status = LlamaCppCapabilityStatus()
    assert status.tokenizer_access == "supported"


def test_decode_access_is_supported() -> None:
    """llama_cpp.Llama.detokenize is confirmed present in llama-cpp-python 0.3.23."""
    status = LlamaCppCapabilityStatus()
    assert status.decode_access == "supported"


def test_greedy_token_via_sample_is_supported() -> None:
    """sample(temp=0.0) is confirmed present as greedy approach."""
    status = LlamaCppCapabilityStatus()
    assert status.greedy_token_via_sample == "supported"


def test_eval_tokens_is_supported() -> None:
    """eval() is confirmed present in llama-cpp-python 0.3.23."""
    status = LlamaCppCapabilityStatus()
    assert status.eval_tokens == "supported"


def test_logits_access_is_partially_supported() -> None:
    """Logits only available with logits_all=True at load time."""
    status = LlamaCppCapabilityStatus()
    assert status.logits_access == "partially_supported"


def test_one_token_step_is_partially_supported() -> None:
    """eval + sample present but not exposed by current LlamaCppBackend wrapper."""
    status = LlamaCppCapabilityStatus()
    assert status.one_token_step == "partially_supported"


def test_wrapper_extension_required_is_partially_supported() -> None:
    """Wrapper extension needed to expose low-level APIs."""
    status = LlamaCppCapabilityStatus()
    assert status.wrapper_extension_required == "partially_supported"


# ---------------------------------------------------------------------------
# 2. Version and metadata
# ---------------------------------------------------------------------------


def test_version_is_recorded() -> None:
    status = LlamaCppCapabilityStatus()
    assert status.llama_cpp_python_version == "0.3.23"


def test_inspection_source_is_recorded() -> None:
    status = LlamaCppCapabilityStatus()
    assert status.inspection_source == "static_source_inspection"


def test_notes_present_for_partially_supported_capabilities() -> None:
    status = LlamaCppCapabilityStatus()
    assert "logits_access" in status.notes
    assert "one_token_step" in status.notes
    assert "wrapper_extension_required" in status.notes
    assert "greedy_token_via_sample" in status.notes


def test_notes_are_non_empty_strings() -> None:
    status = LlamaCppCapabilityStatus()
    for key, note in status.notes.items():
        assert isinstance(note, str) and len(note) > 0, (
            f"Note for {key!r} is empty or not a string"
        )


# ---------------------------------------------------------------------------
# 3. DEFAULT_CAPABILITY_STATUS
# ---------------------------------------------------------------------------


def test_default_capability_status_is_llama_cpp_capability_status() -> None:
    assert isinstance(DEFAULT_CAPABILITY_STATUS, LlamaCppCapabilityStatus)


def test_default_capability_status_is_immutable() -> None:
    with pytest.raises((AttributeError, TypeError)):
        DEFAULT_CAPABILITY_STATUS.tokenizer_access = "blocked"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 4. Optional runtime probe (skip without model)
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="requires real GGUF model — run manually with a loaded Llama instance")
def test_runtime_probe_with_real_model() -> None:
    """Manual test: probe a real loaded llama_cpp.Llama instance."""
    from htfsd.runtime.llama_cpp_capabilities import probe_llama_capabilities

    # This would require loading an actual model — skipped in CI
    # Usage:
    #   from llama_cpp import Llama
    #   model = Llama(model_path="...", n_ctx=512, n_gpu_layers=0)
    #   results = probe_llama_capabilities(model)
    #   assert results["tokenizer_access"] == "supported"
    raise NotImplementedError("Provide a real Llama instance to run this test")
