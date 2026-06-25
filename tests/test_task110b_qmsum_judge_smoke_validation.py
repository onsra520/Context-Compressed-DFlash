from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.phase_2_system_optimization.analysis import task110b_qmsum_judge_smoke_validation as t110b


def test_t110b_parse_json_bounded_strict() -> None:
    text = '{"evidence_support": "yes"}'
    parsed, repaired = t110b.parse_json_bounded(text)
    assert parsed == {"evidence_support": "yes"}
    assert repaired is False


def test_t110b_parse_json_bounded_repair() -> None:
    text = 'Here is your output:\n{"evidence_support": "yes"}\nHope this helps!'
    parsed, repaired = t110b.parse_json_bounded(text)
    assert parsed == {"evidence_support": "yes"}
    assert repaired is True


def test_t110b_parse_json_bounded_invalid() -> None:
    text = 'No JSON here.'
    parsed, repaired = t110b.parse_json_bounded(text)
    assert parsed is None
    assert repaired is False


def test_t110b_analyzer_mock_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yml"
    out_dir = tmp_path / "out"
    t105b_path = tmp_path / "t105b.jsonl"
    t108b_path = tmp_path / "t108b.jsonl"
    dataset_path = tmp_path / "dataset.jsonl"
    
    t110b.ROOT = tmp_path
    
    config_data = {
        "validation_model": {
            "enabled": False,
            "engine": "llama_cpp",
            "model_path": "models/validation/Qwen3.5-9B-GGUF/Qwen3.5-9B-UD-Q4_K_XL.gguf",
            "runtime": {
                "n_ctx": 4096,
                "n_gpu_layers": 0
            }
        }
    }
    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config_data, f)
        
    t110b._write_jsonl(dataset_path, [{"id": "test1", "context": "ctx", "question": "q", "expected_answer": "ans"}])
    t110b._write_jsonl(t105b_path, [{"fixture_id": "test1", "generated_text": "cand1"}])
    t110b._write_jsonl(t108b_path, [{"fixture_id": "test1", "generated_text": "cand2"}])
    
    class MockLlama:
        def __init__(self, *args, **kwargs):
            pass
        def create_chat_completion(self, messages, **kwargs):
            return {"choices": [{"message": {"content": '{"evidence_support": "yes", "final_label": "correct_supported"}'}}]}
            
    # Mock the llama_cpp import by patching sys.modules
    import sys
    import types
    mock_module = types.ModuleType("llama_cpp")
    mock_module.Llama = MockLlama
    sys.modules["llama_cpp"] = mock_module
    
    result = t110b.analyze(
        config_path=config_path,
        output_dir=out_dir,
        t105b_path=t105b_path,
        t108b_path=t108b_path,
        dataset_path=dataset_path
    )
    
    assert result["decision"] == "PASS_WITH_CAVEAT"
    assert result["validation_status"] == "SMOKE_READY"
    assert result["json_parse_audit"]["valid_json_count"] == 2
    
    for path in t110b.OUTPUT_RELATIVE_PATHS:
        assert (out_dir / path).exists()
