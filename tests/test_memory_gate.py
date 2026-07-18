import pytest

from ccdf.runtime.device import current_memory_state, enforce_memory_gate
from ccdf.errors import MemoryBudgetError
from ccdf.schemas import MemoryStats


def test_memory_gate_passes():
    enforce_memory_gate(MemoryStats(peak_reserved_bytes=5, limit_bytes=6, gate_pass=True), label="test")


def test_memory_gate_raises():
    with pytest.raises(MemoryBudgetError):
        enforce_memory_gate(MemoryStats(peak_reserved_bytes=7, limit_bytes=6, gate_pass=False), label="test")


def test_current_memory_state_records_request_boundary(monkeypatch):
    import ccdf.runtime.device as device

    monkeypatch.setattr(device.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(device, "synchronize", lambda *args, **kwargs: None)
    monkeypatch.setattr(device.torch.cuda, "memory_allocated", lambda: 11)
    monkeypatch.setattr(device.torch.cuda, "memory_reserved", lambda: 17)
    assert current_memory_state() == {"allocated_bytes": 11, "reserved_bytes": 17}
