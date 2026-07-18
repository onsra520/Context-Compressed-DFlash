import types
import os

from ccdf.models.loaders import _prepare_awq_compatibility, _prepare_awq_deterministic_kernel


def test_native_jit_fallback_is_selected_before_torch_runtime_import():
    assert os.environ["TORCH_DISABLE_NATIVE_JIT"] == "1"
    assert os.environ["TRITON_CACHE_DIR"] == "/tmp/ccdf-rework-triton-cache"


def test_awq_compatibility_adds_missing_activation_alias(monkeypatch):
    activations = types.SimpleNamespace(GELUTanh=object())
    monkeypatch.setitem(__import__("sys").modules, "transformers.activations", activations)
    assert _prepare_awq_compatibility() is True
    assert activations.PytorchGELUTanh is activations.GELUTanh


def test_deterministic_awq_kernel_forces_single_split(monkeypatch):
    calls = []
    fake = types.SimpleNamespace(
        awq_ext=None,
        TRITON_AVAILABLE=True,
        awq_gemm_triton=lambda *args, **kwargs: calls.append(kwargs["split_k_iters"]),
    )
    monkeypatch.setitem(__import__("sys").modules, "awq.modules.linear.gemm", fake)
    state = _prepare_awq_deterministic_kernel(True)
    fake.awq_gemm_triton(None, split_k_iters=8)
    assert state == {"applied": True, "triton_split_k_iters": 1}
    assert calls == [1]
