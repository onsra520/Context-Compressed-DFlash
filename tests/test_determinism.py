import random

import pytest
import torch

from ccdf.runtime.determinism import configure_determinism


def test_configure_determinism_reseeds_python_and_torch(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    first = configure_determinism(
        seed=42,
        deterministic=True,
        allow_tf32=True,
        matmul_precision="high",
    )
    python_value = random.random()
    torch_value = torch.rand(1)
    second = configure_determinism(
        seed=42,
        deterministic=True,
        allow_tf32=True,
        matmul_precision="high",
    )

    assert random.random() == python_value
    assert torch.equal(torch.rand(1), torch_value)
    assert first["torch_initial_seed"] == second["torch_initial_seed"] == 42
    assert first["deterministic_algorithms"] is True
    assert first["allow_tf32_effective"] is False
    assert first["cublas_workspace_config"] == ":4096:8"


def test_sdpa_policy_records_dispatcher_scope_and_rejects_unknown(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    state = configure_determinism(
        seed=42,
        deterministic=True,
        allow_tf32=False,
        matmul_precision="high",
        sdpa_kernel="auto",
    )
    assert state["configured_sdpa_kernel_policy"] == "auto"
    assert state["actual_kernel_observed"] is False
    assert "availability" in state["dispatcher_state_scope"]
    with pytest.raises(ValueError, match="unsupported SDPA kernel policy"):
        configure_determinism(
            seed=42,
            deterministic=True,
            allow_tf32=False,
            matmul_precision="high",
            sdpa_kernel="flash",
        )
