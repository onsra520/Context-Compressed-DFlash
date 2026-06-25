from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
import yaml

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CONFIG_PATH = ROOT / "config.yml"
DEFAULT_OUTPUT_DIR = ROOT / "results/phase_2_system_optimization/final_reruns/task110a_validation_model_setup"

OUTPUT_RELATIVE_PATHS = (
    "summary/task110a_setup_summary.json",
    "summary/task110a_config_audit.json",
    "summary/task110a_llama_cpp_check.json",
    "summary/task110a_model_file_manifest.json",
    "summary/task110a_claim_update.json",
    "summary/task110a_next_task_decision.json",
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check_llama_cpp() -> dict[str, Any]:
    try:
        import llama_cpp
        return {
            "status": "ok",
            "importable": True,
            "version": getattr(llama_cpp, "__version__", "unknown"),
            "file": getattr(llama_cpp, "__file__", "unknown"),
        }
    except ImportError as e:
        return {
            "status": "error",
            "importable": False,
            "error": str(e),
        }


def analyze(
    config_path: Path = DEFAULT_CONFIG_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    load_smoke: bool = False,
) -> dict[str, Any]:
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
        
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    config_audit = {
        "valid": True,
        "errors": [],
        "target_id": config.get("model", {}).get("target_id"),
        "draft_id": config.get("model", {}).get("draft_id"),
    }
    
    light_device = config.get("compression", {}).get("light_llmlingua", {}).get("device_map")
    if light_device != "cuda":
        config_audit["valid"] = False
        config_audit["errors"].append(f"compression.light_llmlingua.device_map is {light_device}, expected cuda")
        
    val_model = config.get("validation_model")
    if not val_model:
        config_audit["valid"] = False
        config_audit["errors"].append("validation_model block is missing")
    else:
        if val_model.get("engine") != "llama_cpp":
            config_audit["valid"] = False
            config_audit["errors"].append(f"validation_model.engine is {val_model.get('engine')}, expected llama_cpp")
            
        if val_model.get("enabled") is not False:
            config_audit["valid"] = False
            config_audit["errors"].append("validation_model.enabled is not false")
            
        if val_model.get("local_files_only") is not True:
            config_audit["valid"] = False
            config_audit["errors"].append("validation_model.local_files_only is not true")

    llama_status = check_llama_cpp()
    if not llama_status["importable"]:
        config_audit["valid"] = False
        config_audit["errors"].append("llama_cpp is not importable")
        
    model_path_str = val_model.get("model_path") if val_model else None
    model_file_manifest = {
        "exists": False,
        "path": model_path_str,
        "size_bytes": 0,
        "size_gib": 0.0,
        "loaded_smoke_test": False,
    }
    
    if model_path_str:
        absolute_path = ROOT / model_path_str
        if absolute_path.exists() and absolute_path.is_file():
            model_file_manifest["exists"] = True
            size_bytes = absolute_path.stat().st_size
            model_file_manifest["size_bytes"] = size_bytes
            model_file_manifest["size_gib"] = round(size_bytes / (1024**3), 4)
            
            if load_smoke and config_audit["valid"]:
                try:
                    from llama_cpp import Llama
                    _ = Llama(model_path=str(absolute_path), n_gpu_layers=1, n_ctx=512)
                    model_file_manifest["loaded_smoke_test"] = True
                    model_file_manifest["smoke_test_result"] = "success"
                except Exception as e:
                    model_file_manifest["smoke_test_result"] = f"error: {e}"
                    config_audit["valid"] = False
                    config_audit["errors"].append("smoke test failed")
        else:
            config_audit["valid"] = False
            config_audit["errors"].append(f"validation model file not found at {absolute_path}")
            
    claim_update = {
        "allowed_claims": [
            "Local validation model infrastructure is configured using llama_cpp.",
            "T110A setup isolates the judge model from target/draft generation."
        ],
        "blocked_claims": [
            "QMSum is semantically validated.",
            "Default switch is authorized."
        ]
    }
    
    next_task = {
        "next_task": "T110B — QMSum Judge Protocol / Smoke Validation",
        "reason": "Proceed to test the judge prompt and format after setup is validated."
    }
    
    summary = {
        "task": "T110A",
        "title": "Validation Model Setup and Config Wiring",
        "decision": "PASS" if config_audit["valid"] else "FAIL",
        "config_audit": config_audit,
        "llama_cpp_check": llama_status,
        "model_file_manifest": model_file_manifest,
        "claim_update": claim_update,
        "next_task_decision": next_task,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "summary/task110a_setup_summary.json", summary)
    _write_json(output_dir / "summary/task110a_config_audit.json", config_audit)
    _write_json(output_dir / "summary/task110a_llama_cpp_check.json", llama_status)
    _write_json(output_dir / "summary/task110a_model_file_manifest.json", model_file_manifest)
    _write_json(output_dir / "summary/task110a_claim_update.json", claim_update)
    _write_json(output_dir / "summary/task110a_next_task_decision.json", next_task)
    
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--load-smoke", action="store_true")
    args = parser.parse_args()
    
    res = analyze(config_path=args.config, output_dir=args.output_dir, load_smoke=args.load_smoke)
    print(f"decision={res['decision']}")
    print(f"errors={res['config_audit']['errors']}")
    print(f"model_exists={res['model_file_manifest']['exists']}")
    print(f"model_size_gib={res['model_file_manifest']['size_gib']}")
    print(f"llama_cpp_importable={res['llama_cpp_check']['importable']}")


if __name__ == "__main__":
    main()
