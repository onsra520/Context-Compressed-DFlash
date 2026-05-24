from pathlib import Path

import pytest

from htfsd.runtime.llama_cpp_backend import LlamaCppBackend


class FakeLlama:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []

    def __call__(self, prompt: str, **kwargs):
        self.calls.append((prompt, kwargs))
        return {"choices": [{"text": " generated text"}], "usage": {"completion_tokens": 2}}

    def create_chat_completion(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return {
            "choices": [{"message": {"content": " chat text"}}],
            "usage": {"completion_tokens": 3},
        }


def test_backend_exposes_llama_cpp_capabilities(tmp_path: Path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake", encoding="utf-8")

    backend = LlamaCppBackend(
        model_path=model_path,
        n_ctx=1024,
        n_gpu_layers=-1,
        seed=7,
        llama_cls=FakeLlama,
    )

    assert backend.backend_name == "llama.cpp"
    assert backend.model_path == model_path
    assert backend.supports_hidden_states is False


def test_backend_loads_lazily_and_generates_text(tmp_path: Path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake", encoding="utf-8")
    backend = LlamaCppBackend(
        model_path=model_path,
        n_ctx=1024,
        n_gpu_layers=0,
        seed=42,
        llama_cls=FakeLlama,
    )

    result = backend.generate_text("Hello", max_tokens=3, temperature=0.0, stop=["</s>"])

    assert result.text == " generated text"
    assert result.completion_tokens == 2
    assert backend.model is not None
    assert backend.model.kwargs["model_path"] == str(model_path)
    assert backend.model.kwargs["n_ctx"] == 1024
    assert backend.model.kwargs["n_gpu_layers"] == 0
    assert backend.model.kwargs["seed"] == 42
    assert backend.model.calls == [
        ("Hello", {"max_tokens": 3, "temperature": 0.0, "stop": ["</s>"]})
    ]


def test_backend_generates_chat_with_model_template(tmp_path: Path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake", encoding="utf-8")
    backend = LlamaCppBackend(
        model_path=model_path,
        n_ctx=1024,
        n_gpu_layers=0,
        seed=42,
        llama_cls=FakeLlama,
    )

    result = backend.generate_chat(
        [{"role": "user", "content": "Hello"}],
        max_tokens=5,
        temperature=0.0,
        stop=None,
    )

    assert result.text == " chat text"
    assert result.completion_tokens == 3
    assert backend.model.calls == [
        (
            [{"role": "user", "content": "Hello"}],
            {"max_tokens": 5, "temperature": 0.0, "stop": None},
        )
    ]


def test_backend_raises_clear_error_when_llama_cpp_unavailable(tmp_path: Path):
    model_path = tmp_path / "model.gguf"
    model_path.write_text("fake", encoding="utf-8")

    def missing_import():
        raise ImportError("missing llama_cpp")

    backend = LlamaCppBackend(
        model_path=model_path,
        n_ctx=1024,
        n_gpu_layers=-1,
        seed=42,
        import_llama=missing_import,
    )

    with pytest.raises(RuntimeError, match="llama-cpp-python is not available"):
        backend.generate_text("Hello", max_tokens=1)
