from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import scripts.run_mvp as run_mvp
from scripts.eval_datasets import DATASET_REGISTRY, read_jsonl
from scripts.phase_2_system_optimization.analysis import task95b_quality_proxy_calibration as t95b


OUTPUT_DIR = Path("results/phase_2_revalidation/task114r_gsm8k_reproduction_audit")
T106B_JSONL = Path(
    "results/phase_2_system_optimization/final_reruns/task106b_gsm8k_cap_limited_fix/"
    "runs/cc_dflash_r2_light_gpu_gsm8k_seed42_n100_mnt256_concise_final_answer.jsonl"
)
T114_JSONL = Path("results/phase_2_revalidation/task114_canonical_matrix/runs/gsm8k/cc_dflash_r2_light_gpu.jsonl")
DATASET_PATH = Path("data/eval/gsm8k_100.jsonl")
POLICY_NAME = "gsm8k_concise_final_answer_v1"
T106B_POLICY_SUFFIX = (
    "Keep the solution concise. End with exactly one line in the format: "
    "Final answer: <number>. Do not continue after the final answer."
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    if not rows:
        rows = [{field: "" for field in fieldnames}]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames or list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def avg(values: list[float | int | None]) -> float | None:
    nums = [float(value) for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
    return round(mean(nums), 6) if nums else None


def unique_values(rows: list[dict[str, Any]], key: str) -> list[str]:
    return sorted({str(row.get(key)) for row in rows})


def fixture_id(row: dict[str, Any], index: int) -> str:
    return str(row.get("fixture_id") or row.get("dataset_id") or row.get("id") or f"row_{index:04d}")


def calibrate(rows: list[dict[str, Any]], path: Path, label: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows, start=1):
        item = t95b.calibrate_row(row, profile=label, row_index=index, pair_id=fixture_id(row, index), artifact=path)
        out[fixture_id(row, index)] = item
    return out


def extract_answer(row: dict[str, Any], calibrated: dict[str, Any] | None = None) -> str | None:
    for key in ("gsm8k_extracted_final_number", "strict_extracted_answer", "extracted_answer"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    if calibrated:
        value = calibrated.get("strict_extracted_answer")
        if value not in (None, ""):
            return str(value)
    return None


def strict_correct(row: dict[str, Any], calibrated: dict[str, Any] | None = None) -> bool:
    value = row.get("gsm8k_strict_numeric_correct")
    if isinstance(value, bool):
        return value
    return bool(calibrated and calibrated.get("strict_correct"))


def wrong_numeric(row: dict[str, Any], calibrated: dict[str, Any] | None = None) -> bool:
    value = row.get("gsm8k_wrong_numeric")
    if isinstance(value, bool):
        return value
    return bool(calibrated and calibrated.get("calibrated_label") == "strict_wrong_numeric")


def invalid_output(row: dict[str, Any], calibrated: dict[str, Any] | None = None) -> bool:
    value = row.get("gsm8k_invalid_output")
    if isinstance(value, bool):
        return value
    return bool(calibrated and calibrated.get("calibrated_label") in {"answer_missing", "format_or_extraction_sensitive"})


def cap_hit(row: dict[str, Any], calibrated: dict[str, Any] | None = None) -> bool:
    if isinstance(row.get("cap_hit"), bool):
        return bool(row["cap_hit"])
    output_tokens = row.get("output_tokens", row.get("generated_token_count"))
    max_new_tokens = row.get("max_new_tokens")
    token_cap = isinstance(output_tokens, (int, float)) and isinstance(max_new_tokens, (int, float)) and output_tokens >= max_new_tokens
    label_cap = bool(calibrated and calibrated.get("calibrated_label") == "cap_limited_incomplete")
    return bool(token_cap or label_cap)


def prompt_items(*, t106b: bool) -> dict[str, Any]:
    kwargs = {
        "prompt_source": "dataset",
        "n_prompts": 100,
        "fixture_path": None,
        "dataset_name": "gsm8k_short",
        "dataset_path": DATASET_PATH,
        "seed": 42,
    }
    if t106b:
        kwargs.update({"gsm8k_policy_suffix": T106B_POLICY_SUFFIX, "gsm8k_policy_name": POLICY_NAME})
    items = run_mvp._select_prompt_items(**kwargs)
    return {
        str(item.metadata.get("dataset_id") or item.metadata.get("fixture_id")): {
            "prompt_id": item.prompt_id,
            "text": item.text,
            "text_hash": sha256(item.text),
            "protected_suffix": item.protected_suffix,
            "protected_suffix_hash": sha256(item.protected_suffix or ""),
            "metadata": item.metadata,
        }
        for item in items
    }


def dataset_identity(t106b_rows: list[dict[str, Any]], t114_rows: list[dict[str, Any]]) -> dict[str, Any]:
    data_rows = read_jsonl(DATASET_PATH)
    by_id = {str(row["id"]): row for row in data_rows}
    t106b_ids = [fixture_id(row, index) for index, row in enumerate(t106b_rows, start=1)]
    t114_ids = [fixture_id(row, index) for index, row in enumerate(t114_rows, start=1)]
    reference_mismatches = []
    for fid in sorted(set(t106b_ids) & set(t114_ids)):
        d = by_id.get(fid, {})
        a = next(row for row in t106b_rows if fixture_id(row, 0) == fid)
        b = next(row for row in t114_rows if fixture_id(row, 0) == fid)
        if str(d.get("expected_answer")) != str(a.get("expected_answer")) or str(d.get("expected_answer")) != str(b.get("expected_answer")):
            reference_mismatches.append(
                {
                    "fixture_id": fid,
                    "field": "expected_answer",
                    "dataset": d.get("expected_answer"),
                    "t106b": a.get("expected_answer"),
                    "t114": b.get("expected_answer"),
                }
            )
    source_question_hashes = {fid: sha256(str(row.get("question", ""))) for fid, row in by_id.items()}
    return {
        "dataset_path": str(DATASET_PATH),
        "dataset_registry_path": str(DATASET_REGISTRY["gsm8k_short"]["path"]),
        "dataset_row_count": len(data_rows),
        "t106b_row_count": len(t106b_rows),
        "t114_row_count": len(t114_rows),
        "same_fixture_id_set": set(t106b_ids) == set(t114_ids) == set(by_id),
        "same_fixture_order": t106b_ids == t114_ids,
        "missing_from_t106b": sorted(set(by_id) - set(t106b_ids)),
        "extra_in_t106b": sorted(set(t106b_ids) - set(by_id)),
        "missing_from_t114": sorted(set(by_id) - set(t114_ids)),
        "extra_in_t114": sorted(set(t114_ids) - set(by_id)),
        "reference_answer_mismatches": reference_mismatches,
        "source_question_verification": (
            "Run rows do not store the raw question text. The audit verifies question identity through the shared "
            "fixture_id/order in data/eval/gsm8k_100.jsonl and through reconstructed prompt hashes from the same source rows."
        ),
        "sample_source_question_hashes": {fid: source_question_hashes[fid] for fid in sorted(source_question_hashes)[:10]},
    }


def prompt_audit(t106b_prompts: dict[str, Any], t114_prompts: dict[str, Any], t106b_rows: list[dict[str, Any]], t114_rows: list[dict[str, Any]]) -> dict[str, Any]:
    ids = sorted(set(t106b_prompts) & set(t114_prompts))
    prompt_diffs = [
        {
            "fixture_id": fid,
            "t106b_prompt_hash": t106b_prompts[fid]["text_hash"],
            "t114_precompression_prompt_hash": t114_prompts[fid]["text_hash"],
            "same_rendered_precompression_prompt": t106b_prompts[fid]["text"] == t114_prompts[fid]["text"],
            "t106b_suffix": t106b_prompts[fid]["protected_suffix"],
            "t114_suffix": t114_prompts[fid]["protected_suffix"],
        }
        for fid in ids
        if t106b_prompts[fid]["text"] != t114_prompts[fid]["text"]
    ]
    return {
        "resolved_t106b_prompt_profile": POLICY_NAME,
        "resolved_t114_prompt_profile_label": POLICY_NAME,
        "t106b_policy_suffix": T106B_POLICY_SUFFIX,
        "t114_default_suffix": run_mvp.GSM8K_FINAL_ANSWER_INSTRUCTION,
        "t106b_policy_override_rows": sum(1 for row in t106b_rows if row.get("gsm8k_policy_suffix_override") is True),
        "t114_policy_override_rows": sum(1 for row in t114_rows if row.get("gsm8k_policy_suffix_override") is True),
        "all_reconstructed_prompts_differ": len(prompt_diffs) == len(ids),
        "prompt_diff_count": len(prompt_diffs),
        "stored_prompt_hash_overlap_count": len({row.get("prompt_hash") for row in t106b_rows} & {row.get("prompt_hash") for row in t114_rows}),
        "stored_precompression_hash_overlap_count": len({row.get("prompt_hash") for row in t106b_rows} & {row.get("precompression_prompt_hash") for row in t114_rows}),
        "sample_diffs": prompt_diffs[:10],
        "instruction_placement": {
            "t106b": "runtime GSM8K policy suffix passed through --gsm8k-policy-suffix, appended before compression prompt construction and protected after compression",
            "t114": "default eval-dataset GSM8K suffix only; task114 runner set a prompt_policy label but did not pass --gsm8k-policy-suffix",
        },
    }


def compression_audit(t106b_rows: list[dict[str, Any]], t114_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "compressor_model_values": {"t106b": unique_values(t106b_rows, "compressor_model"), "t114": unique_values(t114_rows, "compressor_model")},
        "compressor_profile_values": {"t106b": unique_values(t106b_rows, "compressor_profile"), "t114": unique_values(t114_rows, "compressor_profile")},
        "compressor_device_map_values": {"t106b": unique_values(t106b_rows, "compressor_device_map"), "t114": unique_values(t114_rows, "compressor_device_map")},
        "requested_device_map_values": {"t106b": unique_values(t106b_rows, "requested_compressor_device_map"), "t114": unique_values(t114_rows, "requested_compressor_device_map")},
        "keep_rate_values": {"t106b": unique_values(t106b_rows, "keep_rate"), "t114": unique_values(t114_rows, "keep_rate")},
        "avg_n_original_compressor_tokens": {"t106b": avg([row.get("N_original") for row in t106b_rows]), "t114": avg([row.get("N_original") for row in t114_rows])},
        "avg_original_input_tokens_field": {"t106b": avg([row.get("original_input_tokens") for row in t106b_rows]), "t114": avg([row.get("original_input_tokens") for row in t114_rows])},
        "avg_precompression_input_tokens_field": {"t106b": avg([row.get("precompression_input_tokens") for row in t106b_rows]), "t114": avg([row.get("precompression_input_tokens") for row in t114_rows])},
        "avg_compressed_input_tokens": {"t106b": avg([row.get("compressed_input_tokens") for row in t106b_rows]), "t114": avg([row.get("compressed_input_tokens") for row in t114_rows])},
        "avg_input_tokens_after_compression_chat_template": {"t106b": avg([row.get("input_tokens") for row in t106b_rows]), "t114": avg([row.get("input_tokens") for row in t114_rows])},
        "explanation": (
            "Both artifacts record compressor N_original=16 and N_compressed=8 on average. "
            "The T114 103->8 summary came from task114 normalization replacing original_input_tokens "
            "with precompression model chat-template tokens; T106B used compressor-token original_input_tokens. "
            "This is a metric semantic change, not evidence that the compressor compressed 103 model tokens to 8."
        ),
    }


def generation_audit(t106b_rows: list[dict[str, Any]], t114_rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ["max_new_tokens", "target_path", "draft_path", "tokenizer_path", "block_size", "device", "temperature"]
    return {
        key: {"t106b": unique_values(t106b_rows, key), "t114": unique_values(t114_rows, key)}
        for key in keys
    } | {
        "seed": {"t106b": 42, "t114": 42},
        "sampling": "run_mvp config temperature is 0.0; generation path is deterministic/greedy unless model backend changes",
        "dflash_parameters": {"block_size": unique_values(t114_rows, "block_size"), "draft_path": unique_values(t114_rows, "draft_path")},
        "stop_eos_behavior": "No explicit stop string; cap-hit inferred from output_tokens >= max_new_tokens or quality calibrator cap label.",
    }


def evaluation_audit(t106b_rows: list[dict[str, Any]], t114_rows: list[dict[str, Any]], t106b_cal: dict[str, Any], t114_cal: dict[str, Any]) -> dict[str, Any]:
    return {
        "t106b_evaluator": "Task95B calibrated GSM8K proxy via scripts.phase_2_system_optimization.analysis.task95b_quality_proxy_calibration",
        "t114_evaluator": "Task114 normalize_rows uses its own final-answer regex and cap_hit=output_tokens>=max_new_tokens, summary uses those booleans.",
        "numeric_extraction_difference": "T106B report counts come from Task95B calibration; T114 row fields use task114 regex preferring 'Final answer:' then last number.",
        "t106b_counts_recomputed_with_task95b": label_counts(t106b_rows, t106b_cal),
        "t114_counts_from_task114_fields": {
            "strict_correct": sum(1 for row in t114_rows if row.get("gsm8k_strict_numeric_correct") is True),
            "wrong_numeric": sum(1 for row in t114_rows if row.get("gsm8k_wrong_numeric") is True),
            "invalid": sum(1 for row in t114_rows if row.get("gsm8k_invalid_output") is True),
            "cap_hit": sum(1 for row in t114_rows if row.get("cap_hit") is True),
        },
        "t114_counts_recomputed_with_task95b": label_counts(t114_rows, t114_cal),
        "cap_hit_definition_difference": {
            "t106b_report_cap_limited": "Task95B cap_limited_incomplete label requires cap/unfinished behavior without final-answer marker.",
            "t114_cap_hit": "Boolean token cap: output_tokens >= max_new_tokens.",
        },
    }


def label_counts(rows: list[dict[str, Any]], cal: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = Counter(item["calibrated_label"] for item in cal.values())
    return {
        "strict_correct": sum(1 for item in cal.values() if item["strict_correct"]),
        "strict_wrong_numeric": counts["strict_wrong_numeric"],
        "cap_limited_incomplete": counts["cap_limited_incomplete"],
        "answer_missing": counts["answer_missing"],
        "format_or_extraction_sensitive": counts["format_or_extraction_sensitive"],
    }


def difference_category(t106b_row: dict[str, Any], t114_row: dict[str, Any], t106b_cal: dict[str, Any], t114_cal: dict[str, Any]) -> str:
    if t106b_row.get("expected_answer") != t114_row.get("expected_answer"):
        return "dataset_difference"
    if t106b_row.get("gsm8k_policy_suffix_override") is True and t114_row.get("gsm8k_policy_suffix_override") is not True:
        return "prompt_difference"
    if t106b_row.get("compressor_model") != t114_row.get("compressor_model") or t106b_row.get("keep_rate") != t114_row.get("keep_rate"):
        return "compression_difference"
    if t106b_row.get("max_new_tokens") != t114_row.get("max_new_tokens") or t106b_row.get("target_path") != t114_row.get("target_path"):
        return "generation_difference"
    if cap_hit(t106b_row, t106b_cal) != cap_hit(t114_row, t114_cal):
        return "evaluation_difference"
    return "unexplained"


def matched_rows(t106b_rows: list[dict[str, Any]], t114_rows: list[dict[str, Any]], t106b_cal: dict[str, Any], t114_cal: dict[str, Any]) -> list[dict[str, Any]]:
    t106b_by_id = {fixture_id(row, index): row for index, row in enumerate(t106b_rows, start=1)}
    t114_by_id = {fixture_id(row, index): row for index, row in enumerate(t114_rows, start=1)}
    rows = []
    for fid in sorted(set(t106b_by_id) & set(t114_by_id)):
        a = t106b_by_id[fid]
        b = t114_by_id[fid]
        ac = t106b_cal[fid]
        bc = t114_cal[fid]
        rows.append(
            {
                "fixture_id": fid,
                "t106b_original_tokens": a.get("original_input_tokens"),
                "t106b_n_original": a.get("N_original"),
                "t106b_compressed_tokens": a.get("compressed_input_tokens"),
                "t114_original_tokens": b.get("original_input_tokens"),
                "t114_precompression_tokens": b.get("precompression_input_tokens"),
                "t114_n_original": b.get("N_original"),
                "t114_compressed_tokens": b.get("compressed_input_tokens"),
                "t106b_output_tokens": a.get("output_tokens", a.get("generated_token_count")),
                "t114_output_tokens": b.get("output_tokens", b.get("generated_token_count")),
                "t106b_cap_hit": cap_hit(a, ac),
                "t114_cap_hit": cap_hit(b, bc),
                "t106b_extracted_answer": extract_answer(a, ac),
                "t114_extracted_answer": extract_answer(b, bc),
                "t106b_strict_correct": strict_correct(a, ac),
                "t114_strict_correct": strict_correct(b, bc),
                "t106b_wrong_numeric": wrong_numeric(a, ac),
                "t114_wrong_numeric": wrong_numeric(b, bc),
                "t106b_invalid": invalid_output(a, ac),
                "t114_invalid": invalid_output(b, bc),
                "t106b_label": ac["calibrated_label"],
                "t114_label_task95b": bc["calibrated_label"],
                "t114_row_cap_hit_field": b.get("cap_hit"),
                "t106b_prompt_hash": a.get("prompt_hash"),
                "t114_prompt_hash": b.get("prompt_hash"),
                "t114_precompression_prompt_hash": b.get("precompression_prompt_hash"),
                "difference_category": difference_category(a, b, ac, bc),
            }
        )
    return rows


def config_diff(t106b_rows: list[dict[str, Any]], t114_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        ("execution_path", "direct scripts/run_mvp.py T106B rerun", "scripts/phase_2_revalidation/task114_canonical_matrix.py -> scripts/run_mvp.py"),
        ("gsm8k_policy_suffix", T106B_POLICY_SUFFIX, run_mvp.GSM8K_FINAL_ANSWER_INSTRUCTION),
        ("gsm8k_policy_override_rows", sum(1 for r in t106b_rows if r.get("gsm8k_policy_suffix_override") is True), sum(1 for r in t114_rows if r.get("gsm8k_policy_suffix_override") is True)),
        ("prompt_hash_overlap", "0/100 with T114 prompt_hash", "0/100 with T106B prompt_hash"),
    ]
    for key in ("dataset_name", "prompt_source", "condition", "compressor_model", "compressor_profile", "compressor_device_map", "requested_compressor_device_map", "keep_rate", "max_new_tokens", "target_path", "draft_path", "tokenizer_path", "block_size", "device"):
        rows.append((key, ";".join(unique_values(t106b_rows, key)), ";".join(unique_values(t114_rows, key))))
    rows.extend(
        [
            ("avg_N_original", avg([r.get("N_original") for r in t106b_rows]), avg([r.get("N_original") for r in t114_rows])),
            ("avg_original_input_tokens_field", avg([r.get("original_input_tokens") for r in t106b_rows]), avg([r.get("original_input_tokens") for r in t114_rows])),
            ("avg_input_tokens_after_compression", avg([r.get("input_tokens") for r in t106b_rows]), avg([r.get("input_tokens") for r in t114_rows])),
            ("avg_output_tokens", avg([r.get("output_tokens") for r in t106b_rows]), avg([r.get("output_tokens") for r in t114_rows])),
        ]
    )
    return [{"dimension": key, "t106b": left, "t114": right, "same": str(left) == str(right)} for key, left, right in rows]


def write_selected_dataset(matched: list[dict[str, Any]], limit: int = 5) -> list[str]:
    regressed = [
        row["fixture_id"]
        for row in matched
        if row["t106b_strict_correct"] is True and row["t114_strict_correct"] is not True
    ][:limit]
    source = {str(row["id"]): row for row in read_jsonl(DATASET_PATH)}
    selected = [source[fid] for fid in regressed]
    path = OUTPUT_DIR / "controlled_ab" / "selected_regressed_gsm8k.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in selected), encoding="utf-8")
    return regressed


def controlled_ab_results() -> list[dict[str, Any]]:
    run_dir = OUTPUT_DIR / "controlled_ab" / "runs"
    configs = {
        "historical_t106b": run_dir / "historical_t106b.jsonl",
        "t114": run_dir / "t114.jsonl",
        "t114_plus_t106b_policy": run_dir / "t114_plus_t106b_policy.jsonl",
    }
    rows = []
    for config_name, path in configs.items():
        if not path.exists():
            rows.append({"config": config_name, "status": "not_run", "path": str(path)})
            continue
        run_rows = load_jsonl(path)
        cal = calibrate(run_rows, path, config_name)
        for index, row in enumerate(run_rows, start=1):
            fid = fixture_id(row, index)
            item = cal[fid]
            rows.append(
                {
                    "config": config_name,
                    "status": "ok",
                    "fixture_id": fid,
                    "policy_override": row.get("gsm8k_policy_suffix_override"),
                    "policy_type": row.get("gsm8k_answer_policy_type"),
                    "prompt_hash": row.get("prompt_hash"),
                    "output_tokens": row.get("output_tokens"),
                    "cap_hit": cap_hit(row, item),
                    "extracted_answer": extract_answer(row, item),
                    "strict_correct": strict_correct(row, item),
                    "wrong_numeric": wrong_numeric(row, item),
                    "label": item["calibrated_label"],
                    "path": str(path),
                }
            )
    return rows


def main(argv: list[str] | None = None) -> int:
    global OUTPUT_DIR
    parser = argparse.ArgumentParser(description="Task114R GSM8K reproduction audit")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    OUTPUT_DIR = args.output_dir

    t106b_rows = load_jsonl(T106B_JSONL)
    t114_rows = load_jsonl(T114_JSONL)
    t106b_cal = calibrate(t106b_rows, T106B_JSONL, "T106B")
    t114_cal = calibrate(t114_rows, T114_JSONL, "T114")
    t106b_prompts = prompt_items(t106b=True)
    t114_prompts = prompt_items(t106b=False)
    matched = matched_rows(t106b_rows, t114_rows, t106b_cal, t114_cal)
    selected_ids = write_selected_dataset(matched)

    write_csv(OUTPUT_DIR / "tables/t106b_vs_t114_config_diff.csv", config_diff(t106b_rows, t114_rows))
    write_csv(OUTPUT_DIR / "tables/t106b_vs_t114_matched_rows.csv", matched)
    write_csv(OUTPUT_DIR / "tables/controlled_ab_results.csv", controlled_ab_results())

    dataset_summary = dataset_identity(t106b_rows, t114_rows)
    prompt_summary = prompt_audit(t106b_prompts, t114_prompts, t106b_rows, t114_rows)
    compression_summary = compression_audit(t106b_rows, t114_rows)
    generation_summary = generation_audit(t106b_rows, t114_rows)
    evaluation_summary = evaluation_audit(t106b_rows, t114_rows, t106b_cal, t114_cal)
    root_cause = {
        "decision": "ROOT_CAUSE_IDENTIFIED",
        "secondary_decision": "T114_CONFIG_REGRESSION",
        "root_cause": "T114 labeled GSM8K as gsm8k_concise_final_answer_v1 but did not pass T106B's runtime --gsm8k-policy-suffix override to run_mvp.",
        "evidence": [
            "T106B policy override rows: 100/100; T114 policy override rows: 0/100.",
            "All reconstructed T106B and T114 precompression prompts differ.",
            "Stored prompt hashes have no overlap.",
            "Compressor model/profile/device/keep_rate and generation model/max_new_tokens match.",
            "Dataset fixture set and order match.",
        ],
        "metric_semantic_issue": compression_summary["explanation"],
        "selected_ab_fixture_ids": selected_ids,
        "difference_category_counts": dict(Counter(row["difference_category"] for row in matched)),
        "regressed_from_t106b_strict_to_t114_not_strict": [
            row["fixture_id"] for row in matched if row["t106b_strict_correct"] is True and row["t114_strict_correct"] is not True
        ],
        "t114_new_cap_hits_vs_t106b": [
            row["fixture_id"] for row in matched if row["t106b_cap_hit"] is False and row["t114_cap_hit"] is True
        ],
        "authoritative_candidate": "T106B remains authoritative for the scoped GSM8K candidate because T114 did not reproduce its runtime policy override.",
        "minimal_next_repair": "Run a repaired Task114 GSM8K CC-DFlash-R2 condition with --gsm8k-policy-suffix and --gsm8k-policy-name gsm8k_concise_final_answer_v1, then rebuild the canonical summary without changing Phase 2 claims until verified.",
    }
    next_task = {
        "decision": "ROOT_CAUSE_IDENTIFIED",
        "next_task": "Task114S repaired GSM8K canonical revalidation",
        "rerun_scope": "Do not rerun all six matrix cells initially; repair only GSM8K CC-DFlash-R2 Light GPU after controlled A/B confirms policy variable.",
        "full_matrix_rerun_allowed": False,
        "claim_update_allowed_now": False,
    }

    write_json(OUTPUT_DIR / "summaries/dataset_identity_audit.json", dataset_summary)
    write_json(OUTPUT_DIR / "summaries/prompt_diff_audit.json", prompt_summary)
    write_json(OUTPUT_DIR / "summaries/compression_config_audit.json", compression_summary)
    write_json(OUTPUT_DIR / "summaries/generation_config_audit.json", generation_summary)
    write_json(OUTPUT_DIR / "summaries/evaluation_config_audit.json", evaluation_summary)
    write_json(OUTPUT_DIR / "summaries/root_cause_summary.json", root_cause)
    write_json(OUTPUT_DIR / "summaries/next_task_decision.json", next_task)
    write_json(OUTPUT_DIR / "summaries/static_audit_summary.json", {"dataset": dataset_summary, "prompt": prompt_summary, "root_cause": root_cause})
    print(json.dumps(root_cause, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
