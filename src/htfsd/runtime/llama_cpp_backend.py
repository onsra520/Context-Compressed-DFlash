"""Small llama-cpp-python backend wrapper."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from htfsd.types import TextGenerationResult


class LlamaCppBackend:
    """Lazy wrapper around llama_cpp.Llama for GGUF smoke commands."""

    backend_name = "llama.cpp"
    supports_hidden_states = False

    def __init__(
        self,
        *,
        model_path: str | Path,
        n_ctx: int,
        n_gpu_layers: int,
        seed: int,
        llama_cls: type | None = None,
        import_llama: Callable[[], type] | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.seed = seed
        self._llama_cls = llama_cls
        self._import_llama = import_llama or _import_llama
        self.model = None

    def generate_text(
        self,
        prompt: str,
        *,
        max_tokens: int,
        temperature: float = 0.0,
        stop: Sequence[str] | None = None,
    ) -> TextGenerationResult:
        """Generate text from a prompt with llama.cpp."""

        model = self._load()
        kwargs = {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stop": list(stop) if stop is not None else None,
        }
        raw = model(prompt, **kwargs)
        choice = raw.get("choices", [{}])[0] if isinstance(raw, dict) else {}
        usage = raw.get("usage", {}) if isinstance(raw, dict) else {}
        return TextGenerationResult(
            text=str(choice.get("text", "")),
            completion_tokens=usage.get("completion_tokens"),
        )

    def _load(self):
        if self.model is not None:
            return self.model
        llama_cls = self._llama_cls
        if llama_cls is None:
            try:
                llama_cls = self._import_llama()
            except Exception as error:  # pylint: disable=broad-exception-caught
                raise RuntimeError(
                    "llama-cpp-python is not available. Install it with `uv pip install -e .` "
                    "or verify your Python environment."
                ) from error
        self.model = llama_cls(
            model_path=str(self.model_path),
            n_ctx=self.n_ctx,
            n_gpu_layers=self.n_gpu_layers,
            seed=self.seed,
        )
        return self.model


def _import_llama() -> type:
    from llama_cpp import Llama  # pyright: ignore[reportMissingImports]

    return Llama
