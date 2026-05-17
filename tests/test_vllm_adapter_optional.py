import os

import pytest

from htfsd.runtime.vllm_adapter import VLLM_AVAILABLE, VllmModelHandle, VllmVerificationAdapter


def test_vllm_availability_flag_is_boolean():
    assert isinstance(VLLM_AVAILABLE, bool)


@pytest.mark.vllm
def test_vllm_model_handle_requires_vllm_when_constructed_without_runtime():
    if VLLM_AVAILABLE:
        pytest.skip("This smoke test is for environments with no vLLM imports")
    with pytest.raises(RuntimeError, match="vLLM is not available"):
        VllmModelHandle(model_id_or_path="missing").load()


@pytest.mark.gpu
@pytest.mark.vllm
def test_vllm_verification_adapter_matches_greedy_generation_for_one_token():
    model_path = os.environ.get("HTFSD_TEST_GEMMA_E2B")
    if model_path is None or model_path == "":
        pytest.skip("Set HTFSD_TEST_GEMMA_E2B to run GPU vLLM equivalence test")
    assert model_path is not None

    handle = VllmModelHandle(model_id_or_path=model_path)
    llm = handle.load()
    tokenizer = llm.get_tokenizer()
    adapter = VllmVerificationAdapter(handle, tokenizer)
    context_token_ids = tokenizer.encode("Hello", add_special_tokens=False)

    token = adapter.greedy_next_token(context_token_ids)
    verification = adapter.verify_greedy_prefix(context_token_ids, [token.token_id])

    assert verification.accepted_token_ids == [token.token_id]
    assert verification.reject_position is None
    assert verification.candidate_exhausted is True
