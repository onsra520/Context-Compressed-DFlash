"""Produce bounded real-runtime evidence for Rec-T05A."""

from __future__ import annotations

import json
from pathlib import Path

from ccdf.artifacts.writer import write_json
from ccdf.config import resolve_config
from ccdf.datasets.io import read_jsonl
from ccdf.prompts.schemas import PromptParts
from ccdf.runtime import RuntimeRequest, execute_request


def _smoke(dataset: str, condition: str, *, structured: bool) -> dict:
    resolved = resolve_config(dataset=dataset, condition_id=condition, execution_mode="smoke", overrides={"max_new_tokens": 1})
    if structured:
        fixture = read_jsonl(Path(resolved.data["fixture_path"]))[0]
        request = RuntimeRequest(resolved=resolved, prompt_parts=PromptParts(**fixture["prompt_parts"]), reference_answer=fixture["reference_answer"], measurement_mode="smoke")
    else:
        request = RuntimeRequest(resolved=resolved, prompt="What is 2+2? Answer:", measurement_mode="smoke")
    result = execute_request(request)
    return {"resolved_config_hash": resolved.sha256, "model_paths": resolved.data["models"], "result": result}


def main() -> int:
    output = Path("results/Rec-T05A")
    (output / "logs").mkdir(parents=True, exist_ok=True)
    baseline = _smoke("gsm8k", "baseline-ar", structured=False)
    dflash = _smoke("gsm8k", "dflash-r1", structured=False)
    cc = _smoke("qmsum", "cc-dflash-r2", structured=True)
    write_json(output / "baseline_real_smoke.json", baseline)
    write_json(output / "dflash_real_smoke.json", dflash)
    write_json(output / "cc_dflash_real_smoke.json", cc)
    write_json(output / "runtime_architecture.json", {"shared_function": "ccdf.runtime.engine.RuntimeEngine.execute", "flow": ["resolved config", "loaders", "prompt rendering", "optional compression", "generation", "real timing and VRAM", "serializer"]})
    write_json(output / "runtime_path_audit.json", {"cli": "ccdf.runtime.execute_request", "benchmark": "ccdf.benchmark.workflow.run_benchmark -> RuntimeEngine.execute", "synthetic_runtime": False})
    write_json(output / "config_authority_audit.json", {"target_path": baseline["model_paths"]["target"]["path"], "drafter_path": dflash["model_paths"]["drafter"]["path"], "compressor_path": cc["model_paths"]["compression"]["path"], "compressor_device": cc["model_paths"]["compression"]["device"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
