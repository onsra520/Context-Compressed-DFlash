from __future__ import annotations

import json
import csv
from pathlib import Path


FLAT_CSV_HEADER = [
    "schema_version",
    "run_id",
    "source_type",
    "dataset",
    "split",
    "fixture_id",
    "condition",
    "condition_display_name",
    "prompt_profile",
    "prompt",
    "reference_answer",
    "generated_text",
    "original_input_tokens",
    "compressed_input_tokens",
    "compression_ratio",
    "output_tokens",
    "t_compress_ms",
    "t_prefill_ms",
    "t_generation_ms",
    "t_e2e_ms",
    "generation_tok_s",
    "e2e_tok_s",
    "peak_vram_gib",
    "finish_reason",
    "evaluation_status",
    "numeric_match",
    "normalized_overlap",
    "ok",
    "error_type",
    "error_message"
]


def flatten_result(result: dict) -> dict:
    from ccdf.demo.condition_registry import get_condition
    try:
        cond = get_condition(result["request"]["condition"])
        display_name = cond["display_name"]
    except ValueError:
        display_name = result["request"]["condition"]
        
    return {
        "schema_version": result.get("schema_version"),
        "run_id": result.get("run_id"),
        "source_type": result.get("source", {}).get("type"),
        "dataset": result.get("source", {}).get("dataset"),
        "split": result.get("source", {}).get("split"),
        "fixture_id": result.get("source", {}).get("fixture_id"),
        "condition": result.get("request", {}).get("condition"),
        "condition_display_name": display_name,
        "prompt_profile": result.get("request", {}).get("prompt_profile"),
        "prompt": result.get("request", {}).get("prompt"),
        "reference_answer": result.get("request", {}).get("reference_answer"),
        "generated_text": result.get("response", {}).get("generated_text"),
        "original_input_tokens": result.get("tokens", {}).get("original_input_tokens"),
        "compressed_input_tokens": result.get("tokens", {}).get("compressed_input_tokens"),
        "compression_ratio": result.get("tokens", {}).get("compression_ratio"),
        "output_tokens": result.get("response", {}).get("output_tokens"),
        "t_compress_ms": result.get("timing_ms", {}).get("compression"),
        "t_prefill_ms": result.get("timing_ms", {}).get("prefill"),
        "t_generation_ms": result.get("timing_ms", {}).get("generation"),
        "t_e2e_ms": result.get("timing_ms", {}).get("e2e"),
        "generation_tok_s": result.get("throughput", {}).get("generation_tok_s"),
        "e2e_tok_s": result.get("throughput", {}).get("e2e_tok_s"),
        "peak_vram_gib": result.get("resources", {}).get("peak_vram_gib"),
        "finish_reason": result.get("response", {}).get("finish_reason"),
        "evaluation_status": result.get("quality", {}).get("evaluation_status"),
        "numeric_match": result.get("quality", {}).get("numeric_match"),
        "normalized_overlap": result.get("quality", {}).get("normalized_overlap"),
        "ok": result.get("status", {}).get("ok"),
        "error_type": result.get("status", {}).get("error_type"),
        "error_message": result.get("status", {}).get("error_message"),
    }


def write_json(result: dict | list, path: Path, overwrite: bool = False):
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl_append(result: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")


def write_flat_csv_append(result: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FLAT_CSV_HEADER)
        if write_header:
            writer.writeheader()
        writer.writerow(flatten_result(result))
