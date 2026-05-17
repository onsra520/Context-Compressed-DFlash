import pytest

from htfsd.runtime.vllm_adapter import VLLM_AVAILABLE, VllmModelHandle


def test_vllm_availability_flag_is_boolean():
    assert isinstance(VLLM_AVAILABLE, bool)


@pytest.mark.vllm
def test_vllm_model_handle_requires_vllm_when_constructed_without_runtime():
    if VLLM_AVAILABLE:
        pytest.skip("This smoke test is for environments with no vLLM imports")
    with pytest.raises(RuntimeError, match="vLLM is not available"):
        VllmModelHandle(model_id_or_path="missing").load()
