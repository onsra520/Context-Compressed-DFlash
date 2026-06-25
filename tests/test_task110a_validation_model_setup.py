from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.phase_2_system_optimization.analysis import task110a_validation_model_setup as t110a

def test_t110a_analyzer_valid_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    out_dir = tmp_path / "out"
    model_path = tmp_path / "models/validation/Qwen3.5-9B-GGUF/Qwen3.5-9B-UD-Q4_K_XL.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("dummy model data", encoding="utf-8")
    
    # We must construct a valid path string that resolves correctly in the script
    # The script uses ROOT / path. Since we are testing, we can patch ROOT in the script
    t110a.ROOT = tmp_path
    
    config_data = {
        "model": {
            "target_id": "models/Qwen3-4B",
            "draft_id": "models/Qwen3-4B-DFlash-b16"
        },
        "compression": {
            "light_llmlingua": {
                "device_map": "cuda"
            }
        },
        "validation_model": {
            "enabled": False,
            "engine": "llama_cpp",
            "model_path": "models/validation/Qwen3.5-9B-GGUF/Qwen3.5-9B-UD-Q4_K_XL.gguf",
            "local_files_only": True
        }
    }
    
    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config_data, f)
        
    result = t110a.analyze(config_path=config_path, output_dir=out_dir, load_smoke=False)
    
    assert result["decision"] == "PASS"
    assert result["config_audit"]["valid"] is True
    assert result["model_file_manifest"]["exists"] is True
    assert result["model_file_manifest"]["size_bytes"] > 0
    
    for path in t110a.OUTPUT_RELATIVE_PATHS:
        assert (out_dir / path).exists()

def test_t110a_analyzer_invalid_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yml"
    out_dir = tmp_path / "out"
    t110a.ROOT = tmp_path
    
    config_data = {
        "compression": {
            "light_llmlingua": {
                "device_map": "cpu"
            }
        },
        "validation_model": {
            "enabled": True,
            "engine": "vllm",
            "model_path": "models/validation/missing.gguf",
            "local_files_only": False
        }
    }
    
    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(config_data, f)
        
    result = t110a.analyze(config_path=config_path, output_dir=out_dir, load_smoke=False)
    
    assert result["decision"] == "FAIL"
    assert result["config_audit"]["valid"] is False
    errors = result["config_audit"]["errors"]
    assert any("expected cuda" in e for e in errors)
    assert any("expected llama_cpp" in e for e in errors)
    assert any("is not false" in e for e in errors)
    assert any("is not true" in e for e in errors)
    assert any("validation model file not found" in e for e in errors)

def test_t110a_llama_cpp_check_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_check():
        return {
            "status": "ok",
            "importable": True,
            "version": "test",
            "file": "test",
        }
    monkeypatch.setattr(t110a, "check_llama_cpp", mock_check)
    res = t110a.check_llama_cpp()
    assert res["importable"] is True
