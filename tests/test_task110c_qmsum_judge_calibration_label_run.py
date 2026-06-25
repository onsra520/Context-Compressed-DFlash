from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.phase_2_system_optimization.analysis import task110c_qmsum_judge_calibration_label_run as t110c


def test_t110c_parse_json_bounded_strict() -> None:
    text = '{"evidence_support": "yes"}'
    parsed, repaired = t110c.parse_json_bounded(text)
    assert parsed == {"evidence_support": "yes"}
    assert repaired is False


def test_t110c_analyzer_mock_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.yml"
    out_dir = tmp_path / "out"
    t105b_path = tmp_path / "t105b.jsonl"
    t108b_path = tmp_path / "t108b.jsonl"
    dataset_path = tmp_path / "dataset.jsonl"
    human_labels_path = tmp_path / "human_labels.jsonl"
    
    t110c.ROOT = tmp_path
    
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
        
    t110c._write_jsonl(dataset_path, [{"id": "test1", "context": "ctx", "question": "q", "expected_answer": "ans"}])
    t110c._write_jsonl(t105b_path, [{"fixture_id": "test1", "generated_text": "cand1"}])
    t110c._write_jsonl(t108b_path, [{"fixture_id": "test1", "generated_text": "cand2"}])
    t110c._write_jsonl(human_labels_path, [{"fixture_id": "test1", "human_label": "correct_supported"}])
    
    class MockLlama:
        def __init__(self, *args, **kwargs):
            pass
        def create_chat_completion(self, messages, **kwargs):
            return {"choices": [{"message": {"content": '{"evidence_support": "yes", "final_label": "correct_supported"}'}}]}
            
    import sys
    import types
    mock_module = types.ModuleType("llama_cpp")
    mock_module.Llama = MockLlama
    sys.modules["llama_cpp"] = mock_module
    
    result = t110c.analyze(
        config_path=config_path,
        output_dir=out_dir,
        t105b_path=t105b_path,
        t108b_path=t108b_path,
        dataset_path=dataset_path,
        human_labels_path=human_labels_path
    )
    
    assert result["decision"] == "PASS_WITH_CAVEAT"
    assert result["validation_status"] == "TARGETED_JUDGE_LABELS_READY"
    assert result["json_parse_audit"]["valid_json_count"] == 2
    assert result["human_calibration_comparison"]["alignment_count"] == 1
    
    for path in t110c.OUTPUT_RELATIVE_PATHS:
        assert (out_dir / path).exists()
