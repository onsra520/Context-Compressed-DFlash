from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.eval_datasets import QMSUM_EVIDENCE_FOCUSED_ANSWER_INSTRUCTION
from scripts.phase_2_system_optimization.analysis import task95b_quality_proxy_calibration as t95b

GSM8K_T106B_CONCISE_FINAL_ANSWER_SUFFIX = (
    "Keep the solution concise. End with exactly one line in the format: "
    "Final answer: <number>. Do not continue after the final answer."
)

PROMPT_POLICIES = {
    "gsm8k_concise_final_answer_v1": {
        "dataset_key": "gsm8k",
        "runner_flag": "--gsm8k-policy-suffix",
        "runner_name_flag": "--gsm8k-policy-name",
        "metadata_type": "gsm8k_concise_final_answer_v1",
        "text": GSM8K_T106B_CONCISE_FINAL_ANSWER_SUFFIX,
    },
    "qmsum_t105b_compatible_evidence_focused_v1": {
        "dataset_key": "qmsum",
        "runner_flag": "--qmsum-policy-suffix",
        "runner_name_flag": "--qmsum-policy-name",
        "metadata_type": "evidence_focused",
        "text": QMSUM_EVIDENCE_FOCUSED_ANSWER_INSTRUCTION,
    },
}

OUTPUT_DIR = Path("results/phase_2_revalidation/task114_canonical_matrix")

DATASETS = {
    "gsm8k": {
        "runner_name": "gsm8k_short",
        "path": Path("data/eval/gsm8k_100.jsonl"),
        "max_new_tokens": 256,
        "prompt_policy": "gsm8k_concise_final_answer_v1",
    },
    "qmsum": {
        "runner_name": "qmsum_meeting_qa_long",
        "path": Path("data/eval/qmsum_meeting_qa_100.jsonl"),
        "max_new_tokens": 384,
        "prompt_policy": "qmsum_t105b_compatible_evidence_focused_v1",
    },
}

CONDITIONS = {
    "baseline_ar": {
        "runner_condition": "Baseline-AR",
        "display_name": "Baseline-AR",
        "output_name": "baseline_ar.jsonl",
    },
    "dflash_r1": {
        "runner_condition": "DFlash-R1",
        "display_name": "DFlash-R1",
        "output_name": "dflash_r1.jsonl",
    },
    "cc_dflash_r2_light_gpu": {
        "runner_condition": "CC-DFlash-R2",
        "display_name": "CC-DFlash-R2 Light GPU",
        "output_name": "cc_dflash_r2_light_gpu.jsonl",
        "compressor_profile": "light",
        "compressor_device_map": "cuda",
    },
}

SUMMARY_ORDER = [
    ("gsm8k", "baseline_ar"),
    ("gsm8k", "dflash_r1"),
    ("gsm8k", "cc_dflash_r2_light_gpu"),
    ("qmsum", "baseline_ar"),
    ("qmsum", "dflash_r1"),
    ("qmsum", "cc_dflash_r2_light_gpu"),
]

STOPWORDS = {
    "about", "after", "also", "and", "are", "because", "been", "but", "did", "for",
    "from", "had", "has", "have", "how", "into", "its", "not", "that", "the", "their",
    "then", "there", "they", "this", "was", "were", "what", "when", "which", "who",
    "why", "with", "would",
}


@dataclass(frozen=True)
class RunSpec:
    dataset_key: str
    condition_key: str
    n: int
    output_path: Path

    @property
    def dataset(self) -> dict[str, Any]:
        return DATASETS[self.dataset_key]

    @property
    def condition(self) -> dict[str, Any]:
        return CONDITIONS[self.condition_key]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def dataset_size(dataset_key: str) -> int:
    return len(read_jsonl(DATASETS[dataset_key]["path"]))


def run_file(dataset_key: str, condition_key: str) -> Path:
    return OUTPUT_DIR / "runs" / dataset_key / CONDITIONS[condition_key]["output_name"]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def prompt_policy(dataset_key: str) -> dict[str, str]:
    name = DATASETS[dataset_key]["prompt_policy"]
    policy = PROMPT_POLICIES[name]
    if policy["dataset_key"] != dataset_key:
        raise ValueError(f"prompt policy {name} does not apply to {dataset_key}")
    return policy


def build_command(spec: RunSpec) -> list[str]:
    policy = prompt_policy(spec.dataset_key)
    command = [
        sys.executable,
        "scripts/run_mvp.py",
        "--config",
        "config.yml",
        "--condition",
        spec.condition["runner_condition"],
        "--n",
        str(spec.n),
        "--output",
        str(spec.output_path),
        "--prompt-source",
        "dataset",
        "--dataset",
        spec.dataset["runner_name"],
        "--dataset-path",
        str(spec.dataset["path"]),
        "--seed",
        "42",
        "--max-new-tokens",
        str(spec.dataset["max_new_tokens"]),
        "--warmup-prompts",
        "1",
        "--store-generated-text",
        "--overwrite",
        policy["runner_flag"],
        policy["text"],
        policy["runner_name_flag"],
        spec.dataset["prompt_policy"],
    ]
    if "compressor_profile" in spec.condition:
        command.extend(["--compressor-profile", spec.condition["compressor_profile"]])
    if "compressor_device_map" in spec.condition:
        command.extend(["--compressor-device-map", spec.condition["compressor_device_map"]])
    return command


def execute_run(spec: RunSpec, *, dry_run: bool = False) -> None:
    if dry_run:
        print(" ".join(build_command(spec)))
        return
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = "src" if not existing_pythonpath else f"src{os.pathsep}{existing_pythonpath}"
    subprocess.run(build_command(spec), cwd=ROOT, check=True, env=env)
    rows = normalize_rows(read_jsonl(spec.output_path), spec)
    write_jsonl(spec.output_path, rows)


def _num(row: dict[str, Any], key: str, default: float | None = None) -> float | None:
    value = row.get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _avg(values: list[float | None]) -> float | None:
    nums = [value for value in values if isinstance(value, (int, float)) and math.isfinite(value)]
    return round(mean(nums), 6) if nums else None


def _max(values: list[float | None]) -> float | None:
    nums = [value for value in values if isinstance(value, (int, float)) and math.isfinite(value)]
    return round(max(nums), 6) if nums else None


def extract_gsm8k_number(text: str) -> str | None:
    final_match = re.search(r"final answer\s*:\s*(-?[\d,]+(?:\.\d+)?)", text, flags=re.I)
    matches = [final_match.group(1)] if final_match else re.findall(r"-?[\d,]+(?:\.\d+)?", text)
    if not matches:
        return None
    return matches[-1].replace(",", "")


def normalize_number(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        number = float(value.replace(",", "").strip())
    except ValueError:
        return None
    if number.is_integer():
        return str(int(number))
    return str(number)


def qmsum_proxy(row: dict[str, Any]) -> dict[str, Any]:
    generated = set(_tokens(str(row.get("generated_text", ""))))
    reference = set(_tokens(str(row.get("expected_answer", ""))))
    if not reference:
        return {"qmsum_reference_recall": None, "qmsum_reference_precision": None}
    hits = len(generated & reference)
    return {
        "qmsum_reference_recall": round(hits / len(reference), 6),
        "qmsum_reference_precision": round(hits / len(generated), 6) if generated else 0.0,
    }


def _tokens(text: str) -> list[str]:
    return [
        token for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2 and token not in STOPWORDS
    ]


def normalize_rows(rows: list[dict[str, Any]], spec: RunSpec) -> list[dict[str, Any]]:
    normalized = []
    policy = prompt_policy(spec.dataset_key)
    policy_name = spec.dataset["prompt_policy"]
    policy_text = policy["text"]
    policy_hash = sha256_text(policy_text)
    for row in rows:
        row = dict(row)
        if policy_text not in " ".join(
            str(row.get(key, ""))
            for key in (
                "protected_suffix_preview",
                "gsm8k_output_policy_preview",
                "qmsum_output_policy_preview",
                "final_prompt_tail_preview",
                "original_prompt_preview",
            )
        ):
            # Previews can be truncated, so require explicit metadata for compressed rows
            # and add canonical metadata for uncompressed rows from the resolved runner policy.
            if spec.condition_key == "cc_dflash_r2_light_gpu" and row.get("protected_suffix_preserved") is not True:
                raise ValueError(f"{spec.dataset_key}/{spec.condition_key}: resolved policy was not preserved")
        if spec.dataset_key == "gsm8k":
            if row.get("gsm8k_answer_policy_type") not in (None, policy_name):
                raise ValueError(f"unexpected GSM8K policy type: {row.get('gsm8k_answer_policy_type')}")
            row.update(
                {
                    "gsm8k_policy_suffix_override": True,
                    "gsm8k_answer_policy_enabled": True,
                    "gsm8k_answer_policy_type": policy_name,
                    "gsm8k_answer_policy_preserved": True,
                    "gsm8k_output_policy_preview": policy_text,
                }
            )
        else:
            if row.get("qmsum_answer_policy_type") not in (None, policy_name, policy["metadata_type"]):
                raise ValueError(f"unexpected QMSum policy type: {row.get('qmsum_answer_policy_type')}")
            row.update(
                {
                    "qmsum_policy_suffix_override": True,
                    "qmsum_answer_policy_enabled": True,
                    "qmsum_answer_policy_type": policy_name,
                    "qmsum_t105b_compatible_policy": True,
                    "qmsum_answer_policy_preserved": True,
                    "qmsum_output_policy_preview": policy_text,
                    "qmsum_evidence_focus_enabled": True,
                    "qmsum_evidence_focus_version": "task77",
                }
            )
        original = _num(row, "precompression_input_tokens", _num(row, "input_tokens", 0.0)) or 0.0
        compressed = _num(row, "compressed_input_tokens")
        if spec.condition_key != "cc_dflash_r2_light_gpu":
            compressed = None
            retained = reduction = factor = None
            row["t_compress_ms"] = 0.0
        else:
            if compressed is None:
                compressed = _num(row, "input_tokens", 0.0)
            retained = compressed / original if original else None
            reduction = (1.0 - retained) * 100.0 if retained is not None else None
            factor = original / compressed if compressed else None
        row.update(
            {
                "task_id": "T114",
                "dataset": spec.dataset_key,
                "dataset_name": spec.dataset["runner_name"],
                "condition_key": spec.condition_key,
                "display_name": spec.condition["display_name"],
                "prompt_policy": policy_name,
                "resolved_prompt_policy": policy_name,
                "resolved_prompt_policy_text": policy_text,
                "resolved_prompt_policy_hash": policy_hash,
                "precompression_rendered_prompt_hash": row.get("precompression_prompt_hash") or row.get("prompt_hash"),
                "original_input_tokens": int(original),
                "compressed_input_tokens": int(compressed) if compressed is not None else None,
                "compression_retained_ratio": retained,
                "compression_reduction_pct": reduction,
                "compression_factor": factor,
                "t_generation_ms": _num(row, "t_generation_ms", (_num(row, "generation_time_s", 0.0) or 0.0) * 1000.0),
                "peak_allocated_gib": _num(row, "peak_allocated_gib", _num(row, "vram_allocated_gib", 0.0)),
                "peak_reserved_gib": _num(row, "peak_reserved_gib", _num(row, "vram_reserved_gib", 0.0)),
                "cap_hit": bool(row.get("cap_hit")) or ((_num(row, "output_tokens", 0.0) or 0.0) >= (_num(row, "max_new_tokens", 1.0) or 1.0)),
                "full_generated_text_present": bool(str(row.get("generated_text", "")).strip()),
            }
        )
        row["t_e2e_ms"] = (
            (_num(row, "t_compress_ms", 0.0) or 0.0)
            + (_num(row, "t_prefill_ms", 0.0) or 0.0)
            + (_num(row, "t_generation_ms", 0.0) or 0.0)
        )
        row["e2e_time_s"] = row["t_e2e_ms"] / 1000.0
        row["finish_reason"] = "length_cap" if row["cap_hit"] else str(row.get("finish_reason") or "eos_or_stop")
        if spec.dataset_key == "gsm8k":
            calibrated = t95b.calibrate_row(
                row,
                profile="T114H GSM8K calibrated",
                row_index=int(row.get("benchmark_prompt_index") or row.get("prompt_id") or 0),
                pair_id=row.get("fixture_id") or row.get("dataset_id") or row.get("benchmark_prompt_index"),
                artifact=spec.output_path,
            )
            extracted = normalize_number(str(calibrated.get("strict_extracted_answer"))) if calibrated.get("strict_extracted_answer") is not None else normalize_number(extract_gsm8k_number(str(row.get("generated_text", ""))))
            expected = normalize_number(str(calibrated.get("expected_numeric"))) if calibrated.get("expected_numeric") is not None else normalize_number(str(row.get("expected_answer", "")))
            label = calibrated.get("calibrated_label")
            row.update(
                {
                    "gsm8k_extracted_final_number": extracted,
                    "gsm8k_expected_number": expected,
                    "gsm8k_strict_numeric_correct": bool(calibrated.get("strict_correct")),
                    "gsm8k_wrong_numeric": label == "strict_wrong_numeric",
                    "gsm8k_invalid_output": label in {"answer_missing", "format_or_extraction_sensitive", "proxy_uncertain"},
                    "gsm8k_calibrated_label": label,
                    "gsm8k_final_answer_marker_present": bool(calibrated.get("final_answer_marker_present")),
                }
            )
            row["cap_hit"] = row["cap_hit"] or label == "cap_limited_incomplete"
            row["finish_reason"] = "length_cap" if row["cap_hit"] else str(row.get("finish_reason") or "eos_or_stop")
        else:
            row.update(qmsum_proxy(row))
            row["qmsum_invalid_output"] = not str(row.get("generated_text", "")).strip()
        normalized.append(row)
    return normalized


def audit_smoke(paths: dict[tuple[str, str], Path]) -> dict[str, Any]:
    failures: list[str] = []
    rows_by_dataset_condition = {key: read_jsonl(path) for key, path in paths.items()}
    for dataset_key in DATASETS:
        by_index: dict[int, list[dict[str, Any]]] = {}
        for condition_key in CONDITIONS:
            for row in rows_by_dataset_condition[(dataset_key, condition_key)]:
                by_index.setdefault(int(row["benchmark_prompt_index"]), []).append(row)
        for index, rows in by_index.items():
            hashes = {row.get("precompression_prompt_hash") for row in rows}
            tokens = {row.get("precompression_input_tokens") for row in rows}
            if len(rows) != 3:
                failures.append(f"{dataset_key}:{index}: expected 3 condition rows")
            if len(hashes) != 1:
                failures.append(f"{dataset_key}:{index}: precompression prompt hash mismatch")
            if len(tokens) != 1:
                failures.append(f"{dataset_key}:{index}: precompression token mismatch")
            policy_hashes = {row.get("resolved_prompt_policy_hash") for row in rows}
            if len(policy_hashes) != 1:
                failures.append(f"{dataset_key}:{index}: resolved prompt policy hash mismatch")
    for (dataset_key, condition_key), rows in rows_by_dataset_condition.items():
        policy = prompt_policy(dataset_key)
        for row in rows:
            if row.get("resolved_prompt_policy") != DATASETS[dataset_key]["prompt_policy"]:
                failures.append(f"{dataset_key}/{condition_key}: resolved policy name mismatch")
            if row.get("resolved_prompt_policy_hash") != sha256_text(policy["text"]):
                failures.append(f"{dataset_key}/{condition_key}: resolved policy hash mismatch")
            if row.get("resolved_prompt_policy_text") != policy["text"]:
                failures.append(f"{dataset_key}/{condition_key}: resolved policy text mismatch")
            if row.get("is_warmup") is not False or int(row.get("warmup_prompts", 0)) < 1:
                failures.append(f"{dataset_key}/{condition_key}: warmup contract not recorded")
            if not row.get("full_generated_text_present"):
                failures.append(f"{dataset_key}/{condition_key}: generated text missing")
            if row.get("peak_allocated_gib") is None or row.get("peak_reserved_gib") is None:
                failures.append(f"{dataset_key}/{condition_key}: VRAM separation missing")
            expected_e2e = row["t_compress_ms"] + row["t_prefill_ms"] + row["t_generation_ms"]
            if abs(row["t_e2e_ms"] - expected_e2e) > 1e-6:
                failures.append(f"{dataset_key}/{condition_key}: t_e2e_ms composition invalid")
            if condition_key == "cc_dflash_r2_light_gpu":
                if row.get("compressor_profile") != "light":
                    failures.append(f"{dataset_key}/{condition_key}: light compressor not used")
                if str(row.get("compressor_device_map")) not in {"cuda", "cuda:0"}:
                    failures.append(f"{dataset_key}/{condition_key}: CUDA compressor not used")
                original = row["original_input_tokens"]
                compressed = row["compressed_input_tokens"]
                if not original or not compressed:
                    failures.append(f"{dataset_key}/{condition_key}: compression token fields missing")
                else:
                    retained = compressed / original
                    factor = original / compressed
                    if abs(row["compression_retained_ratio"] - retained) > 1e-6:
                        failures.append(f"{dataset_key}/{condition_key}: retained-ratio formula invalid")
                    if abs(row["compression_factor"] - factor) > 1e-6:
                        failures.append(f"{dataset_key}/{condition_key}: compression-factor formula invalid")
            elif row.get("t_compress_ms") != 0.0:
                failures.append(f"{dataset_key}/{condition_key}: uncompressed t_compress_ms not zero")
            if dataset_key == "gsm8k" and "gsm8k_strict_numeric_correct" not in row:
                failures.append(f"{dataset_key}/{condition_key}: GSM8K quality fields missing")
            if dataset_key == "gsm8k" and row.get("gsm8k_answer_policy_type") != DATASETS[dataset_key]["prompt_policy"]:
                failures.append(f"{dataset_key}/{condition_key}: GSM8K runtime policy missing")
            if dataset_key == "qmsum" and "qmsum_reference_recall" not in row:
                failures.append(f"{dataset_key}/{condition_key}: QMSum proxy fields missing")
            if dataset_key == "qmsum" and row.get("qmsum_answer_policy_type") != DATASETS[dataset_key]["prompt_policy"]:
                failures.append(f"{dataset_key}/{condition_key}: QMSum runtime policy missing")
    return {"passed": not failures, "failures": failures}


def summarize(rows_by_key: dict[tuple[str, str], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    summary = []
    for dataset_key, condition_key in SUMMARY_ORDER:
        rows = rows_by_key[(dataset_key, condition_key)]
        base = {
            "dataset": dataset_key,
            "condition": condition_key,
            "display_name": CONDITIONS[condition_key]["display_name"],
            "run_path": str(run_file(dataset_key, condition_key)),
            "resolved_prompt_policy": DATASETS[dataset_key]["prompt_policy"],
            "resolved_prompt_policy_hash": sha256_text(prompt_policy(dataset_key)["text"]),
            "row_policy_hash_unique_count": len({row.get("resolved_prompt_policy_hash") for row in rows}),
            "row_count": len(rows),
            "success_count": sum(1 for row in rows if row.get("full_generated_text_present") and not row.get("error")),
            "avg_original_input_tokens": _avg([_num(row, "original_input_tokens") for row in rows]),
            "avg_compressed_input_tokens": _avg([_num(row, "compressed_input_tokens") for row in rows]),
            "avg_compression_retained_ratio": _avg([_num(row, "compression_retained_ratio") for row in rows]),
            "avg_compression_reduction_pct": _avg([_num(row, "compression_reduction_pct") for row in rows]),
            "avg_t_compress_ms": _avg([_num(row, "t_compress_ms", 0.0) for row in rows]),
            "avg_t_prefill_ms": _avg([_num(row, "t_prefill_ms") for row in rows]),
            "avg_t_generation_ms": _avg([_num(row, "t_generation_ms") for row in rows]),
            "avg_t_e2e_ms": _avg([_num(row, "t_e2e_ms") for row in rows]),
            "avg_generation_tok_s": _avg([_num(row, "tokens_per_second") for row in rows]),
            "avg_e2e_tok_s": _avg([(_num(row, "output_tokens") or 0.0) / ((_num(row, "t_e2e_ms") or 1.0) / 1000.0) for row in rows]),
            "max_peak_allocated_gib": _max([_num(row, "peak_allocated_gib") for row in rows]),
            "max_peak_reserved_gib": _max([_num(row, "peak_reserved_gib") for row in rows]),
            "cap_hit_count": sum(1 for row in rows if row.get("cap_hit")),
        }
        if dataset_key == "gsm8k":
            base.update(
                {
                    "gsm8k_strict_numeric_correct_count": sum(1 for row in rows if row.get("gsm8k_strict_numeric_correct")),
                    "gsm8k_wrong_numeric_count": sum(1 for row in rows if row.get("gsm8k_wrong_numeric")),
                    "gsm8k_invalid_output_count": sum(1 for row in rows if row.get("gsm8k_invalid_output")),
                }
            )
        else:
            base.update(
                {
                    "qmsum_avg_reference_recall": _avg([_num(row, "qmsum_reference_recall") for row in rows]),
                    "qmsum_avg_reference_precision": _avg([_num(row, "qmsum_reference_precision") for row in rows]),
                    "qmsum_invalid_output_count": sum(1 for row in rows if row.get("qmsum_invalid_output")),
                    "qmsum_semantic_correctness_claimed": False,
                }
            )
        summary.append(base)
    return summary


def per_row_audit(rows_by_key: dict[tuple[str, str], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for dataset_key, condition_key in SUMMARY_ORDER:
        for row in rows_by_key[(dataset_key, condition_key)]:
            rows.append(
                {
                    "dataset": dataset_key,
                    "condition": condition_key,
                    "benchmark_prompt_index": row.get("benchmark_prompt_index"),
                    "precompression_prompt_hash": row.get("precompression_prompt_hash"),
                    "precompression_rendered_prompt_hash": row.get("precompression_rendered_prompt_hash"),
                    "resolved_prompt_policy": row.get("resolved_prompt_policy"),
                    "resolved_prompt_policy_hash": row.get("resolved_prompt_policy_hash"),
                    "precompression_input_tokens": row.get("precompression_input_tokens"),
                    "original_input_tokens": row.get("original_input_tokens"),
                    "compressed_input_tokens": row.get("compressed_input_tokens"),
                    "t_compress_ms": row.get("t_compress_ms"),
                    "t_prefill_ms": row.get("t_prefill_ms"),
                    "t_generation_ms": row.get("t_generation_ms"),
                    "t_e2e_ms": row.get("t_e2e_ms"),
                    "peak_allocated_gib": row.get("peak_allocated_gib"),
                    "peak_reserved_gib": row.get("peak_reserved_gib"),
                    "cap_hit": row.get("cap_hit"),
                    "finish_reason": row.get("finish_reason"),
                }
            )
    return rows


def write_manifests(rows_by_key: dict[tuple[str, str], list[dict[str, Any]]], smoke_audit: dict[str, Any]) -> None:
    manifests = OUTPUT_DIR / "manifests"
    first_rows = [rows[0] for rows in rows_by_key.values() if rows]
    datasets_manifest = {
        key: {field: str(value) if isinstance(value, Path) else value for field, value in config.items()}
        for key, config in DATASETS.items()
    }
    write_json(
        manifests / "component_manifest.json",
        {
            "task_id": "T114",
            "runner": "scripts/phase_2_revalidation/task114_canonical_matrix.py",
            "source_runner": "scripts/run_mvp.py",
            "datasets": datasets_manifest,
            "prompt_policies": {
                key: {
                    "name": config["prompt_policy"],
                    "text_hash": sha256_text(prompt_policy(key)["text"]),
                    "text": prompt_policy(key)["text"],
                }
                for key, config in DATASETS.items()
            },
            "conditions": CONDITIONS,
            "models": {
                "target_paths": sorted({str(row.get("target_path")) for row in first_rows}),
                "draft_paths": sorted({str(row.get("draft_path")) for row in first_rows if row.get("draft_path")}),
                "tokenizer_paths": sorted({str(row.get("tokenizer_path")) for row in first_rows}),
            },
        },
    )
    write_json(manifests / "prompt_fairness_audit.json", smoke_audit)
    write_json(
        manifests / "timing_metric_audit.json",
        {
            "t_e2e_ms_formula": "t_compress_ms + t_prefill_ms + t_generation_ms",
            "model_load_and_warmup_excluded": True,
            "rows_are_not_warmup": all(not row.get("is_warmup") for rows in rows_by_key.values() for row in rows),
        },
    )
    write_json(
        manifests / "vram_metric_audit.json",
        {
            "allocated_and_reserved_are_separate": all(
                row.get("peak_allocated_gib") is not None and row.get("peak_reserved_gib") is not None
                for rows in rows_by_key.values()
                for row in rows
            ),
            "fields": ["peak_allocated_gib", "peak_reserved_gib"],
        },
    )


def write_summaries(rows_by_key: dict[tuple[str, str], list[dict[str, Any]]], summary_rows: list[dict[str, Any]], smoke_audit: dict[str, Any]) -> None:
    summaries = OUTPUT_DIR / "summaries"
    write_json(summaries / "task114_summary.json", {"task_id": "T114", "smoke_gate": smoke_audit, "summary_rows": summary_rows})
    for dataset_key in DATASETS:
        write_json(summaries / f"{dataset_key}_summary.json", [row for row in summary_rows if row["dataset"] == dataset_key])
    write_json(
        summaries / "final_claim_boundary.json",
        {
            "t111_preserved_as_historical_complete_with_caveats": True,
            "phase_2_revalidation_reopened": True,
            "production_default_switch_authorized": False,
            "qmsum_semantic_correctness_claimed": False,
            "claim_boundary": "Task114 reports source-runner metrics and bounded quality proxies only.",
        },
    )


def collect_rows(*, write_back: bool = False) -> dict[tuple[str, str], list[dict[str, Any]]]:
    rows_by_key = {}
    for dataset_key, condition_key in SUMMARY_ORDER:
        path = run_file(dataset_key, condition_key)
        rows = normalize_rows(read_jsonl(path), RunSpec(dataset_key, condition_key, dataset_size(dataset_key), path))
        if write_back:
            write_jsonl(path, rows)
        rows_by_key[(dataset_key, condition_key)] = rows
    return rows_by_key


def build_artifacts(smoke_paths: dict[tuple[str, str], Path]) -> dict[str, Any]:
    rows_by_key = collect_rows(write_back=True)
    smoke_audit = audit_smoke(smoke_paths)
    summary_rows = summarize(rows_by_key)
    write_csv(OUTPUT_DIR / "tables" / "three_condition_two_dataset_summary.csv", summary_rows)
    write_csv(OUTPUT_DIR / "tables" / "per_row_metric_audit.csv", per_row_audit(rows_by_key))
    write_manifests(rows_by_key, smoke_audit)
    write_summaries(rows_by_key, summary_rows, smoke_audit)
    return {"smoke_audit": smoke_audit, "summary_rows": summary_rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Task114 canonical two-dataset, three-condition revalidation runner.")
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--full-only", action="store_true")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dataset", choices=["all", *DATASETS.keys()], default="all")
    args = parser.parse_args(argv)
    selected_summary_order = [
        (dataset_key, condition_key)
        for dataset_key, condition_key in SUMMARY_ORDER
        if args.dataset == "all" or dataset_key == args.dataset
    ]

    smoke_paths: dict[tuple[str, str], Path] = {}
    if args.build_only:
        for dataset_key, condition_key in SUMMARY_ORDER:
            smoke_paths[(dataset_key, condition_key)] = OUTPUT_DIR / "smoke" / dataset_key / CONDITIONS[condition_key]["output_name"]
        result = build_artifacts(smoke_paths)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if not args.full_only:
        for dataset_key, condition_key in selected_summary_order:
            path = OUTPUT_DIR / "smoke" / dataset_key / CONDITIONS[condition_key]["output_name"]
            smoke_paths[(dataset_key, condition_key)] = path
            execute_run(RunSpec(dataset_key, condition_key, 1, path), dry_run=args.dry_run)
        if args.dry_run:
            return 0
        smoke_audit = audit_smoke(smoke_paths)
        write_json(OUTPUT_DIR / "manifests" / "prompt_fairness_audit.json", smoke_audit)
        if not smoke_audit["passed"]:
            print(json.dumps(smoke_audit, indent=2, sort_keys=True))
            return 1
        if args.smoke_only:
            print(json.dumps(smoke_audit, indent=2, sort_keys=True))
            return 0
    else:
        for dataset_key, condition_key in SUMMARY_ORDER:
            smoke_paths[(dataset_key, condition_key)] = OUTPUT_DIR / "smoke" / dataset_key / CONDITIONS[condition_key]["output_name"]

    for dataset_key, condition_key in selected_summary_order:
        execute_run(RunSpec(dataset_key, condition_key, dataset_size(dataset_key), run_file(dataset_key, condition_key)), dry_run=args.dry_run)
    if args.dry_run:
        return 0
    result = build_artifacts(smoke_paths)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
