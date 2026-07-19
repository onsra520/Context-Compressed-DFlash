import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ccdf.compression.llmlingua import (
    adaptive_keep_rate,
    compress_samples,
    compression_success_counts,
    run_safeguarded_attempts,
)
from ccdf.config import load_config
from ccdf.config.model import Rec2Config
from ccdf.config.validation import validate_config
from ccdf.core.errors import ConfigurationError


def _validation(passed: bool) -> SimpleNamespace:
    return SimpleNamespace(
        to_dict=lambda: {
            "passed": passed,
            "checks": {"fact_numbers": passed},
            "failure_reasons": [] if passed else ["fact_numbers"],
            "diagnostic_failures": [],
        }
    )


@pytest.mark.parametrize(
    ("tokens", "rate"),
    [(0, 0.85), (127, 0.85), (128, 0.70), (512, 0.70), (513, 0.55)],
)
def test_length_based_keep_rate_policy(tokens: int, rate: float) -> None:
    assert adaptive_keep_rate(load_config("config.yml"), tokens) == rate


def test_adaptive_retry_uses_point_nine_after_fact_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    outcomes = iter([False, True])
    monkeypatch.setattr(
        "ccdf.compression.llmlingua.safeguard_prompt_batch",
        lambda _text, _compress: SimpleNamespace(validation=_validation(next(outcomes))),
    )
    result, attempts = run_safeguarded_attempts("prompt", [0.85, 0.90], lambda values, rate: values)

    assert result is not None
    assert [row["keep_rate"] for row in attempts] == [0.85, 0.90]
    assert [row["fact_validation_passed"] for row in attempts] == [False, True]


def test_failed_retry_signals_fallback_and_is_not_compression_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ccdf.compression.llmlingua.safeguard_prompt_batch",
        lambda _text, _compress: SimpleNamespace(validation=_validation(False)),
    )
    result, attempts = run_safeguarded_attempts("prompt", [0.85, 0.90], lambda values, rate: values)
    row = {
        "status": "fallback",
        "compression_applied": False,
        "compression_status": "FACT_SAFETY_FALLBACK",
        "fallback_reason": "fact validation failed after adaptive retry",
        "attempted_keep_rates": [item["keep_rate"] for item in attempts],
    }

    assert result is None
    assert row["attempted_keep_rates"] == [0.85, 0.90]
    assert compression_success_counts([row]) == {
        "successful_compressions": 0,
        "fallback_samples": 1,
        "failed_samples": 0,
    }


def test_full_compress_samples_returns_explicit_fallback_after_two_failed_validations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Integration coverage for the full cache-row path, including the former None dereference."""
    model_path = tmp_path / "compressor"
    model_path.mkdir()
    (model_path / "config.json").write_text("{}\n", encoding="utf-8")
    config = load_config("config.yml")
    data = copy.deepcopy(config.data)
    data["models"]["compressor"]["local_path"] = str(model_path)
    test_config = Rec2Config(path=config.path, root=config.root, data=data)
    observed_rates: list[float] = []

    class FakeTokenizer:
        def __call__(self, text: str, *, add_special_tokens: bool = False) -> dict:
            return {"input_ids": list(range(len(text.split())))}

    class FakePromptCompressor:
        def __init__(self, **_kwargs: object) -> None:
            self.model = object()
            self.tokenizer = FakeTokenizer()
            self.max_batch_size = 1

        def compress_prompt_llmlingua2(self, texts: list[str], *, rate: float, **_kwargs: object) -> dict:
            observed_rates.append(rate)
            return {"compressed_prompt_list": texts}

    def always_fail(_text: str, compress: object) -> SimpleNamespace:
        compress(["candidate span"])
        return SimpleNamespace(validation=_validation(False))

    memory = SimpleNamespace(
        peak_allocated_bytes=1024,
        peak_reserved_bytes=2048,
        gate_pass=True,
    )
    monkeypatch.setattr("llmlingua.PromptCompressor", FakePromptCompressor)
    monkeypatch.setattr("transformers.AutoTokenizer.from_pretrained", lambda *_args, **_kwargs: FakeTokenizer())
    monkeypatch.setattr("ccdf.compression.llmlingua.safeguard_prompt_batch", always_fail)
    monkeypatch.setattr("ccdf.compression.llmlingua.torch.cuda.is_available", lambda: True)
    monkeypatch.setattr("ccdf.compression.llmlingua.torch.cuda.device_count", lambda: 1)
    monkeypatch.setattr("ccdf.compression.llmlingua.torch.cuda.set_device", lambda _index: None)
    monkeypatch.setattr("ccdf.compression.llmlingua.torch.cuda.get_device_name", lambda _index: "fake-cuda")
    monkeypatch.setattr("ccdf.compression.llmlingua.synchronize", lambda *_args: None)
    monkeypatch.setattr("ccdf.compression.llmlingua.reset_peak_memory", lambda: None)
    monkeypatch.setattr("ccdf.compression.llmlingua.collect_memory", lambda **_kwargs: memory)
    monkeypatch.setattr("ccdf.compression.llmlingua._placement", lambda *_args, **_kwargs: ("cuda:0", ["float32"]))
    monkeypatch.setattr("ccdf.compression.llmlingua._close", lambda _compressor: None)

    original = "Compute 7 + 5. End with: Final answer: <number>"
    rows, audit = compress_samples(
        test_config,
        [{"dataset": "gsm8k", "split": "test", "sample_id": "forced-fallback", "prompt": original}],
        output_path=tmp_path / "cache.jsonl",
    )

    assert observed_rates == [0.85, 0.90]
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "fallback"
    assert row["compressed_prompt"] == original
    assert row["compression_applied"] is False
    assert row["compression_status"] == "FACT_SAFETY_FALLBACK"
    assert row["fallback_reason"]
    assert row["attempted_keep_rates"] == [0.85, 0.90]
    assert audit["status"] == "success"
    assert audit["successful_compressions"] == 0
    assert audit["fallback_samples"] == 1
    assert audit["failed_samples"] == 0
    assert audit["usable_samples"] == 1

    resumed_rows, resumed_audit = compress_samples(
        test_config,
        [{"dataset": "gsm8k", "split": "test", "sample_id": "forced-fallback", "prompt": original}],
        output_path=tmp_path / "cache.jsonl",
        resume=True,
    )

    assert observed_rates == [0.85, 0.90]
    assert resumed_rows == rows
    assert resumed_audit["resumed_samples"] == 1
    assert resumed_audit["new_samples"] == 0


def test_config_runtime_qmsum_policy_consistency() -> None:
    config = load_config("config.yml")
    validate_config(config)
    data = copy.deepcopy(config.data)
    data["datasets"]["qmsum_context_policy"] = "full_transcript"
    inconsistent = Rec2Config(path=Path("config.yml"), root=config.root, data=data)

    with pytest.raises(ConfigurationError, match="query_aware_budgeted"):
        validate_config(inconsistent)


def test_qmsum_hash_contract_is_shared_across_conditions() -> None:
    selected = "selected-hash"
    compressed = "compressed-hash"
    rows = [
        {
            "condition_id": condition,
            "selected_context_sha256": selected,
            "compressed_context_sha256": compressed,
        }
        for condition in ("C1", "C2", "C3", "C4")
    ]
    assert len({row["selected_context_sha256"] for row in rows}) == 1
    assert len({row["compressed_context_sha256"] for row in rows if row["condition_id"] in {"C3", "C4"}}) == 1


def test_qmsum_selection_and_compression_metrics_are_separate() -> None:
    full, selected, compressed = 2000, 800, 600
    metrics = {
        "selection_keep_rate": selected / full,
        "llmlingua_keep_rate": compressed / selected,
        "overall_keep_rate": compressed / full,
    }
    assert metrics == {
        "selection_keep_rate": 0.4,
        "llmlingua_keep_rate": 0.75,
        "overall_keep_rate": 0.3,
    }
