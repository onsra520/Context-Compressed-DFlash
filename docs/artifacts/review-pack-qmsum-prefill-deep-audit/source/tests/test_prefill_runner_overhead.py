from types import SimpleNamespace

import torch

from ccdf.protocols import orchestrator
from ccdf.runtime import engine as engine_module
from ccdf.runtime.engine import RuntimeEngine


class _Config:
    _values = {
        "memory.request_cache_policy": "retain",
        "runtime.max_new_tokens": 1,
        "runtime.temperature": 0.0,
        "runtime.stop_token_ids": [],
        "optimization.block_policy.fixed_block_size": 8,
        "optimization.output_contract_mode": "plain",
    }

    def require(self, key: str):
        return self._values[key]


def test_capture_chat_template_encodes_once_and_times_audit_separately(monkeypatch):
    calls = 0

    class FakeEngine:
        tokenizer = SimpleNamespace(name_or_path="unit-tokenizer")

        def encode_prompt(self, prompt: str) -> torch.Tensor:
            nonlocal calls
            calls += 1
            assert prompt == "hello"
            return torch.tensor([[1, 2, 3]])

    monkeypatch.setattr(orchestrator, "synchronize", lambda: None)
    evidence, input_ids = orchestrator._capture_chat_template_input(FakeEngine(), "hello")

    assert calls == 1
    assert evidence["token_ids"] == [1, 2, 3]
    assert evidence["token_count"] == 3
    assert evidence["chat_template_calls"] == 1
    assert evidence["encoding_ms"] >= 0
    assert evidence["token_audit_ms"] >= 0
    assert input_ids.tolist() == [[1, 2, 3]]


def test_runtime_generate_reuses_preencoded_input_and_forwards_progress(monkeypatch):
    runtime = object.__new__(RuntimeEngine)
    runtime.config = _Config()
    runtime.condition = "baseline"
    runtime.model = object()
    runtime.tokenizer = object()
    runtime.model_metadata = {}
    runtime.allocator_policy = {}
    runtime.determinism = {}
    runtime._configure_determinism = lambda: {"seed": 42}
    runtime.encode_prompt = lambda prompt: (_ for _ in ()).throw(
        AssertionError("pre-encoded request must not encode again")
    )
    input_ids = SimpleNamespace(device=SimpleNamespace(type="cuda"))
    progress_callback = object()
    captured = {}
    result = SimpleNamespace(
        runtime={},
        timing=SimpleNamespace(prompt_prepare_ms=None, warm_request_ms=None),
    )

    def fake_generate_baseline(model, tokenizer, actual_input_ids, settings, **kwargs):
        captured["input_ids"] = actual_input_ids
        captured["progress_callback"] = kwargs["progress_callback"]
        return result

    monkeypatch.setattr(engine_module, "generate_baseline", fake_generate_baseline)
    monkeypatch.setattr(engine_module, "synchronize", lambda *args, **kwargs: None)

    actual = RuntimeEngine.generate(
        runtime,
        "unused",
        input_ids=input_ids,
        prompt_prepare_ms=12.5,
        progress_callback=progress_callback,
        max_new_tokens=1,
    )

    assert actual is result
    assert captured["input_ids"] is input_ids
    assert captured["progress_callback"] is progress_callback
    assert result.timing.prompt_prepare_ms == 12.5
    assert result.runtime["inference_tensor_audit"]["input_ids_cuda"] is True
