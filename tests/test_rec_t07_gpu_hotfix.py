from __future__ import annotations

import sys
import subprocess
from types import SimpleNamespace

import pytest

from ccdf.compression.llmlingua import LLMLinguaCompressor
from ccdf.runtime.engine import _resource_composition


class _Device:
    def __init__(self, name: str) -> None:
        self.type = name.split(":", 1)[0]
        self._name = name

    def __str__(self) -> str:
        return self._name


class _Tensor:
    def __init__(self, device: str, size: int = 2) -> None:
        self.device = _Device(device)
        self._size = size

    def numel(self) -> int:
        return self._size

    def element_size(self) -> int:
        return 4


class _Owner:
    def __init__(self, parameters: list[_Tensor], buffers: list[_Tensor]) -> None:
        self._parameters = parameters
        self._buffers = buffers

    def parameters(self):
        return iter(self._parameters)

    def buffers(self):
        return iter(self._buffers)


def _compressor(parameters: list[_Tensor], buffers: list[_Tensor]) -> LLMLinguaCompressor:
    compressor = LLMLinguaCompressor.__new__(LLMLinguaCompressor)
    compressor.backend = SimpleNamespace(model=_Owner(parameters, buffers))
    compressor.device_audit = compressor._audit_devices()
    return compressor


def test_cuda_audit_counts_all_parameters_and_buffers(monkeypatch: pytest.MonkeyPatch) -> None:
    compressor = _compressor([_Tensor("cuda:0"), _Tensor("cuda:0", 3)], [_Tensor("cuda:0")])
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True)))
    assert compressor.device_audit["unique_devices"] == ["cuda:0"]
    assert compressor.device_audit["total_parameters"] == compressor.device_audit["cuda_parameters"] == 2
    assert compressor.device_audit["total_buffers"] == compressor.device_audit["cuda_buffers"] == 1
    assert compressor.device_audit["execution_mode"] == "resident"
    assert compressor._verify_cuda() is True


def test_cuda_audit_rejects_one_cpu_tensor(monkeypatch: pytest.MonkeyPatch) -> None:
    compressor = _compressor([_Tensor("cuda:0"), _Tensor("cpu")], [])
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True)))
    assert compressor.device_audit["unique_devices"] == ["cpu", "cuda:0"]
    assert compressor.device_audit["execution_mode"] == "staged"
    assert compressor._verify_cuda() is False


@pytest.mark.parametrize("condition", ["llmlingua-ar-r2-gpu", "cc-dflash-r2-gpu"])
def test_gpu_composition_is_explicit_when_compressor_is_resident(condition: str) -> None:
    _, model = _resource_composition(condition, False)
    assert model.endswith("GPU compressor")


@pytest.mark.parametrize("condition", ["llmlingua-ar-r2-gpu", "cc-dflash-r2-gpu"])
def test_gsm8k_bypass_composition_never_claims_loaded_gpu_compressor(condition: str) -> None:
    resource, model = _resource_composition(condition, True)
    assert "bypassed and not loaded" in resource
    assert "bypassed and not loaded" in model


def test_runtime_resource_contract_has_real_gpu_delta_and_execution_metadata() -> None:
    source = open("src/ccdf/runtime/engine.py", encoding="utf-8").read()
    assert '"compressor_gpu_bytes": self.compressor_cuda_allocated_delta_bytes' in source
    assert '"compressor_execution_mode"' in source
    assert '"compressor_transfer_to_device_ms"' in source


def test_combined_summary_has_cpu_gpu_speedup_and_claim_boundary() -> None:
    report = open("results/Rec-T07/combined_report.md", encoding="utf-8").read()
    summary = open("results/Rec-T07/combined_summary.csv", encoding="utf-8").read()
    assert "18.56x" in report and "NOT_CLAIMED" in report
    assert "compression_speedup_vs_cpu" in summary
    assert "llmlingua-ar-r2-gpu" in summary and "cc-dflash-r2-gpu" in summary


def test_readme_parser_commands_work_from_a_clean_directory(tmp_path) -> None:
    root = __import__("pathlib").Path.cwd()
    environment = {"PATH": __import__("os").environ["PATH"], "PYTHONPATH": str(root / "src")}
    for arguments in (("--help",), ("paths", "--help"), ("run", "--help"), ("benchmark", "--help"), ("evaluate", "--help")):
        completed = subprocess.run(
            [sys.executable, "-m", "ccdf", *arguments], cwd=tmp_path, env=environment,
            capture_output=True, text=True, check=False,
        )
        assert completed.returncode == 0, completed.stderr
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "/home/" not in readme and "/data/Projects/" not in readme
