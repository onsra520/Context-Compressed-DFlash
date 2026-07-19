from pathlib import Path

import pytest

from ccdf.compression.llmlingua import _device_index, _placement, append_jsonl
from ccdf.core.errors import ModelContractError


class _Tensor:
    def __init__(self, device: str, *, floating: bool = True) -> None:
        self.device = device
        self.dtype = "torch.float16"
        self._floating = floating

    def is_floating_point(self) -> bool:
        return self._floating


class _Model:
    def __init__(self, parameters: list[_Tensor], buffers: list[_Tensor]) -> None:
        self._parameters = parameters
        self._buffers = buffers

    def parameters(self):
        return iter(self._parameters)

    def buffers(self):
        return iter(self._buffers)


def test_compressor_gpu_contract_checks_parameters_and_buffers() -> None:
    model = _Model([_Tensor("cuda:0")], [_Tensor("cuda:0")])

    device, dtypes = _placement(model, expected_index=0)

    assert device == "cuda:0"
    assert dtypes == ["float16"]


@pytest.mark.parametrize("device", ["cpu", "cuda:1"])
def test_compressor_gpu_contract_rejects_cpu_or_wrong_cuda_device(device: str) -> None:
    model = _Model([_Tensor("cuda:0")], [_Tensor(device)])

    with pytest.raises(ModelContractError, match="not fully resident"):
        _placement(model, expected_index=0)


def test_compressor_device_request_forbids_silent_cpu_fallback() -> None:
    with pytest.raises(ModelContractError, match="must be CUDA"):
        _device_index("cpu")


def test_durable_jsonl_append_preserves_prior_rows(tmp_path: Path) -> None:
    path = tmp_path / "cache.jsonl"

    append_jsonl(path, {"row": 1})
    append_jsonl(path, {"row": 2})

    assert path.read_text(encoding="utf-8").splitlines() == ["{\"row\": 1}", "{\"row\": 2}"]
