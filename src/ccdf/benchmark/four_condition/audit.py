"""Manifest-driven independent audit for four-condition evidence."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any

from .conditions import CONDITIONS
from .manifest import expected_key, manifest_sample_map, validate_manifest
from .runner import read_jsonl
from .schema import D_FLASH_ONLY, validate_record

_FINAL_NUMERIC = re.compile(
    r"Final answer:\s*([-+]?\$?[\d,]+(?:\.\d+)?)\.?\s*$", re.IGNORECASE
)
_WORD = re.compile(r"[A-Za-z0-9]+")


def _describe(values: list[float]) -> dict[str, float | int] | None:
    if not values:
        return None
    if any(not math.isfinite(value) for value in values):
        raise ValueError("metric series must contain finite values")
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def raw_key(row: dict[str, Any]) -> tuple[str, str, str, int | None, int]:
    return (
        str(row["condition_id"]), str(row["sample_id"]), str(row["phase"]),
        row["repetition"], int(row["request_index"]),
    )


def duplicate_keys(rows: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    counts = Counter(raw_key(row) for row in rows)
    return sorted(key for key, count in counts.items() if count > 1)


def _unique_pair_index(rows: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    keys = [(str(row["sample_id"]), int(row["repetition"])) for row in rows]
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate parity keys: {duplicates}")
    return {key: row for key, row in zip(keys, rows, strict=True)}


def _pair_parity(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    left_by_key = _unique_pair_index(left)
    right_by_key = _unique_pair_index(right)
    rows = []
    for key in sorted(set(left_by_key) | set(right_by_key)):
        lhs = left_by_key.get(key)
        rhs = right_by_key.get(key)
        lhs_ids = lhs["generated_token_ids"] if lhs and lhs["status"] == "success" else []
        rhs_ids = rhs["generated_token_ids"] if rhs and rhs["status"] == "success" else []
        mismatch = next(
            (index for index in range(min(len(lhs_ids), len(rhs_ids))) if lhs_ids[index] != rhs_ids[index]),
            min(len(lhs_ids), len(rhs_ids)) if len(lhs_ids) != len(rhs_ids) else None,
        )
        rows.append(
            {
                "sample_id": key[0], "repetition": key[1],
                "present_both": lhs is not None and rhs is not None,
                "both_success": bool(lhs and rhs and lhs["status"] == rhs["status"] == "success"),
                "input_prompt_parity": bool(lhs and rhs and lhs["input_prompt_sha256"] == rhs["input_prompt_sha256"]),
                "input_token_parity": bool(
                    lhs and rhs
                    and lhs["target_user_original_tokens"] == rhs["target_user_original_tokens"]
                    and lhs["target_user_compressed_tokens"] == rhs["target_user_compressed_tokens"]
                    and lhs["target_full_original_tokens"] == rhs["target_full_original_tokens"]
                    and lhs["target_full_compressed_tokens"] == rhs["target_full_compressed_tokens"]
                ),
                "generated_token_parity": bool(lhs and rhs and lhs_ids == rhs_ids),
                "first_mismatch_index": mismatch,
                "left_mismatch_token_id": lhs_ids[mismatch] if mismatch is not None and mismatch < len(lhs_ids) else None,
                "right_mismatch_token_id": rhs_ids[mismatch] if mismatch is not None and mismatch < len(rhs_ids) else None,
                "left_row_type": (
                    lhs["generated_token_sources"][mismatch]
                    if lhs and mismatch is not None and mismatch < len(lhs_ids)
                    else None
                ),
                "right_row_type": (
                    rhs["generated_token_sources"][mismatch]
                    if rhs and mismatch is not None and mismatch < len(rhs_ids)
                    else None
                ),
                "left_decoded_output": lhs["decoded_output"] if mismatch is not None and lhs else None,
                "right_decoded_output": rhs["decoded_output"] if mismatch is not None and rhs else None,
                "left_parsed_answer": lhs["parsed_answer"] if mismatch is not None and lhs else None,
                "right_parsed_answer": rhs["parsed_answer"] if mismatch is not None and rhs else None,
                "left_quality_score": lhs["quality_score"] if mismatch is not None and lhs else None,
                "right_quality_score": rhs["quality_score"] if mismatch is not None and rhs else None,
                "task_answer_or_quality_preserved": bool(
                    mismatch is not None
                    and lhs
                    and rhs
                    and (
                        (
                            lhs["dataset"] == "canonical_mock"
                            and lhs["quality_score"] == rhs["quality_score"] == 1.0
                        )
                        or (
                            lhs["dataset"] == "gsm8k"
                            and lhs["parser_status"] == rhs["parser_status"] == "parsed"
                            and lhs["parsed_answer"] == rhs["parsed_answer"]
                        )
                        or (
                            lhs["dataset"] == "qmsum"
                            and bool(str(lhs["decoded_output"]).strip())
                            and bool(str(rhs["decoded_output"]).strip())
                        )
                    )
                ),
            }
        )
    return rows


def _condition_pair_ids(manifest: dict[str, Any], prompt_kind: str) -> tuple[str, str]:
    rows = [row for row in manifest["conditions"] if row["prompt_kind"] == prompt_kind]
    baseline = [row["condition_id"] for row in rows if row["runtime_condition"] == "baseline"]
    dflash = [row["condition_id"] for row in rows if row["runtime_condition"] == "dflash"]
    if len(baseline) != 1 or len(dflash) != 1:
        raise ValueError(f"manifest does not define one {prompt_kind} baseline/DFlash pair")
    return baseline[0], dflash[0]


def _recompute_row(row: dict[str, Any], *, tolerance: float = 1e-9) -> list[str]:
    if row["status"] != "success":
        return []
    failures = []
    expected_pipeline = row["generation_warm_e2e_time_ms"] + (row["compressor_latency_ms"] or 0.0)
    expected_generation_rate = row["generated_token_count"] / (row["generation_warm_e2e_time_ms"] / 1000.0)
    expected_pipeline_rate = row["generated_token_count"] / (row["pipeline_warm_e2e_time_ms"] / 1000.0)
    calculations = {
        "pipeline_warm_e2e_time_ms": expected_pipeline,
        "generation_e2e_tok_s": expected_generation_rate,
        "pipeline_e2e_tok_s": expected_pipeline_rate,
        "target_user_token_reduction": row["target_user_original_tokens"] - row["target_user_compressed_tokens"],
        "target_user_keep_rate": row["target_user_compressed_tokens"] / row["target_user_original_tokens"],
        "target_user_compression_ratio": row["target_user_original_tokens"] / row["target_user_compressed_tokens"],
        "target_full_token_reduction": row["target_full_original_tokens"] - row["target_full_compressed_tokens"],
        "target_full_keep_rate": row["target_full_compressed_tokens"] / row["target_full_original_tokens"],
        "target_full_compression_ratio": row["target_full_original_tokens"] / row["target_full_compressed_tokens"],
        "compressor_token_keep_rate": row["compressor_compressed_tokens"] / row["compressor_original_tokens"],
    }
    for name, expected in calculations.items():
        actual = row[name]
        if not math.isclose(float(actual), float(expected), rel_tol=tolerance, abs_tol=tolerance):
            failures.append(name)
    failures.extend(_recompute_quality(row, tolerance=tolerance))
    return failures


def _normalize_numeric(value: str) -> str | None:
    try:
        number = Decimal(value.replace("$", "").replace(",", "").strip())
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    normalized = format(number.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return "0" if normalized in {"-0", "+0", ""} else normalized


def _independent_gsm_parse(text: str) -> tuple[str | None, str]:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return None, "empty_output"
    match = _FINAL_NUMERIC.search(text)
    if match is None:
        return None, "missing_final_answer_line"
    value = _normalize_numeric(match.group(1))
    return (value, "parsed") if value is not None else (None, "invalid_numeric")


def _independent_rouge_l(text: str, reference: str) -> dict[str, float | int | bool]:
    prediction = [match.group(0).lower() for match in _WORD.finditer(text)]
    truth = [match.group(0).lower() for match in _WORD.finditer(reference)]
    previous = [0] * (len(truth) + 1)
    for token in prediction:
        current = [0]
        for index, truth_token in enumerate(truth, start=1):
            current.append(previous[index - 1] + 1 if token == truth_token else max(previous[index], current[-1]))
        previous = current
    lcs = previous[-1]
    precision = lcs / len(prediction) if prediction else 0.0
    recall = lcs / len(truth) if truth else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "quality_score": f1,
        "lcs_tokens": lcs,
        "prediction_tokens": len(prediction),
        "reference_tokens": len(truth),
        "empty_output": not bool(prediction),
    }


def _recompute_quality(row: dict[str, Any], *, tolerance: float) -> list[str]:
    dataset = row["dataset"]
    if dataset == "canonical_mock":
        expected = float(bool(row["quality"] and row["quality"]["quality_pass"]))
        return [] if math.isclose(float(row["quality_score"]), expected, rel_tol=tolerance, abs_tol=tolerance) else ["quality_score"]
    if dataset == "gsm8k":
        parsed, status = _independent_gsm_parse(str(row["decoded_output"]))
        reference = _normalize_numeric(str(row["reference_text"]))
        score = float(parsed is not None and parsed == reference)
        failures = []
        if row["parsed_answer"] != parsed:
            failures.append("parsed_answer")
        if row["parser_status"] != status:
            failures.append("parser_status")
        if not math.isclose(float(row["quality_score"]), score, rel_tol=tolerance, abs_tol=tolerance):
            failures.append("quality_score")
        return failures
    if dataset == "qmsum":
        expected = _independent_rouge_l(str(row["decoded_output"]), str(row["reference_text"]))
        failures = []
        if not math.isclose(float(row["quality_score"]), float(expected["quality_score"]), rel_tol=tolerance, abs_tol=tolerance):
            failures.append("quality_score")
        details = row["quality_details"]
        for field in ("lcs_tokens", "prediction_tokens", "reference_tokens", "empty_output"):
            if details.get(field) != expected[field]:
                failures.append(f"quality_details.{field}")
        return failures
    return []


def _parsed_agreement(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> bool:
    left_by_key = _unique_pair_index(left)
    right_by_key = _unique_pair_index(right)
    if set(left_by_key) != set(right_by_key) or not left_by_key:
        return False
    return all(
        left_by_key[key]["status"] == right_by_key[key]["status"] == "success"
        and left_by_key[key]["parser_status"] == right_by_key[key]["parser_status"] == "parsed"
        and left_by_key[key]["parsed_answer"] == right_by_key[key]["parsed_answer"]
        for key in left_by_key
    )


def summarize_errors(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [row for row in rows if row.get("status") == "failed"]
    return {
        "runtime_error_count": len(failures),
        "by_stage": dict(sorted(Counter(row["failure_stage"] for row in failures).items())),
        "by_type": dict(sorted(Counter(row["failure_type"] for row in failures).items())),
        "rows": [
            {
                "key": raw_key(row), "stage": row["failure_stage"],
                "type": row["failure_type"], "message": row["failure_message"],
            }
            for row in failures
        ],
    }


def audit(
    *,
    condition_paths: dict[str, Path],
    compression_path: Path,
    compressor_audit_path: Path,
    isolation_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_manifest(manifest)
    expected_conditions = [row["condition_id"] for row in manifest["conditions"]]
    if set(condition_paths) != set(expected_conditions):
        raise ValueError("condition paths do not match run manifest")
    all_rows = {condition: read_jsonl(condition_paths[condition]) for condition in expected_conditions}
    flat_rows = [row for condition in expected_conditions for row in all_rows[condition]]
    compression = read_jsonl(compression_path)
    compressor = json.loads(compressor_audit_path.read_text(encoding="utf-8"))
    isolation = json.loads(isolation_path.read_text(encoding="utf-8"))
    schema_errors = []
    for index, row in enumerate(flat_rows):
        try:
            validate_record(row)
        except Exception as exc:
            schema_errors.append({"row_index": index, "error": str(exc)})
    duplicates = duplicate_keys(flat_rows) if not schema_errors else []
    actual_keys = [raw_key(row) for row in flat_rows] if not schema_errors else []
    expected_keys = [expected_key(row) for row in manifest["expected_records"]]
    missing_keys = sorted(set(expected_keys) - set(actual_keys))
    unexpected_keys = sorted(set(actual_keys) - set(expected_keys))
    expected_order = {
        condition: [expected_key(row) for row in manifest["expected_records"] if row["condition_id"] == condition]
        for condition in expected_conditions
    }
    actual_order = {
        condition: [raw_key(row) for row in all_rows[condition]] if not schema_errors else []
        for condition in expected_conditions
    }
    cache_ids = [str(row["sample_id"]) for row in compression]
    duplicate_cache_ids = sorted(key for key, count in Counter(cache_ids).items() if count > 1)
    expected_sample_ids = list(manifest["workload"]["sample_ids"])
    cache_order_match = cache_ids == expected_sample_ids
    cache_by_id = {row["sample_id"]: row for row in compression} if not duplicate_cache_ids else {}
    manifest_samples = manifest_sample_map(manifest)
    cache_hash_match = bool(cache_by_id) and all(
        cache_by_id[sample_id]["original_prompt_sha256"] == manifest_samples[sample_id]["prompt_sha256"]
        and cache_by_id[sample_id]["compressed_prompt_sha256"]
        == hashlib.sha256(str(cache_by_id[sample_id]["compressed_prompt"]).encode("utf-8")).hexdigest()
        and cache_by_id[sample_id]["status"] in {"success", "fallback"}
        for sample_id in expected_sample_ids
        if sample_id in cache_by_id
    ) and set(cache_by_id) == set(expected_sample_ids)
    row_identity_match = not schema_errors and all(
        row["run_id"] == manifest["run_id"]
        and row["manifest_sha256"] == manifest["manifest_sha256"]
        and row["condition_id"] in expected_conditions
        and row["original_prompt_sha256"] == manifest_samples[row["sample_id"]]["prompt_sha256"]
        and hashlib.sha256(str(row["original_prompt_text"]).encode("utf-8")).hexdigest()
        == manifest_samples[row["sample_id"]]["prompt_sha256"]
        and row["task_type"] == manifest_samples[row["sample_id"]].get("task_type")
        and row["source_fingerprint"] == manifest_samples[row["sample_id"]].get("source_fingerprint")
        and row["prompt_version"] == manifest_samples[row["sample_id"]].get("prompt_version")
        and (
            row["status"] != "success"
            or hashlib.sha256(str(row["input_prompt_text"]).encode("utf-8")).hexdigest()
            == row["input_prompt_sha256"]
        )
        for row in flat_rows
    )
    measured = {
        condition: [row for row in all_rows[condition] if row.get("phase") == "measured"]
        for condition in expected_conditions
    }
    original_left, original_right = _condition_pair_ids(manifest, "original")
    compressed_left, compressed_right = _condition_pair_ids(manifest, "compressed")
    parity_safe = not schema_errors and not duplicates and not missing_keys and not unexpected_keys
    parity = {
        "original": _pair_parity(measured[original_left], measured[original_right]) if parity_safe else [],
        "compressed": _pair_parity(measured[compressed_left], measured[compressed_right]) if parity_safe else [],
    }
    calculation_failures = [
        {"key": raw_key(row), "fields": failed}
        for row in flat_rows
        if (failed := _recompute_row(row))
    ] if not schema_errors else []
    failures = [row for row in flat_rows if row.get("status") == "failed"]
    error_summary = summarize_errors(flat_rows)
    process_ids = {
        condition: sorted({int(row["process_id"]) for row in all_rows[condition]})
        for condition in expected_conditions
    }
    compression_runs = {row["compression_run_id"] for row in compression}
    compressed_reuse = parity_safe and all(
        row["compression_run_id"] in compression_runs
        and row["compressed_prompt_sha256"] == cache_by_id[row["sample_id"]]["compressed_prompt_sha256"]
        and hashlib.sha256(str(row["compressed_prompt_text"]).encode("utf-8")).hexdigest()
        == cache_by_id[row["sample_id"]]["compressed_prompt_sha256"]
        for condition in (compressed_left, compressed_right)
        for row in measured[condition]
    )
    successful_measured = [row for rows in measured.values() for row in rows if row["status"] == "success"]
    compressed_success = [row for condition in (compressed_left, compressed_right) for row in measured[condition] if row["status"] == "success"]
    dataset_names = sorted({str(row["dataset"]) for row in flat_rows})
    if len(dataset_names) != 1:
        raise ValueError(f"one run manifest must contain exactly one dataset: {dataset_names}")
    dataset = dataset_names[0]
    canonical_quality_rows = [row for row in successful_measured if row["dataset"] == "canonical_mock"]
    quality_contract_valid = all(
        row["quality_score"] is not None
        and math.isfinite(float(row["quality_score"]))
        and row["parser_status"] in {
            "parsed", "empty_output", "missing_final_answer_line", "invalid_numeric", "not_applicable"
        }
        for row in successful_measured
    )
    gates = {
        "manifest_valid": True,
        "unified_schema": not schema_errors,
        "raw_unique": not duplicates,
        "raw_complete": not missing_keys and not unexpected_keys and len(actual_keys) == len(expected_keys),
        "raw_order": all(actual_order[c] == expected_order[c] for c in expected_conditions),
        "row_identity_and_prompt_hash": row_identity_match,
        "condition_success": not failures and len(flat_rows) == len(expected_keys),
        "compression_unique_complete_ordered": not duplicate_cache_ids and cache_order_match,
        "compression_hash_and_status": cache_hash_match,
        "compression_once_per_sample": len(compression_runs) == 1 and len(compression) == manifest["expected_counts"]["compression_rows"],
        "fact_safety_resolved": bool(compression) and all(
            (
                row["status"] == "success"
                and row["compression_applied"] is True
                and row["safeguard_validation"]
                and row["safeguard_validation"]["passed"]
            )
            or (
                row["status"] == "fallback"
                and row["compression_applied"] is False
                and row["compression_status"] == "FACT_SAFETY_FALLBACK"
                and bool(row["fallback_reason"])
            )
            for row in compression
        ),
        "compressed_prompt_reused": compressed_reuse,
        "compressor_gpu": compressor["status"] == "success" and compressor["requested_device"].startswith("cuda") and compressor["resolved_device"].startswith("cuda") and compressor["silent_cpu_fallback"] is False,
        "condition_process_isolation": all(len(ids) == 1 for ids in process_ids.values()) and len({ids[0] for ids in process_ids.values()}) == len(expected_conditions),
        "gpu_release_between_conditions": len(isolation.get("boundaries", [])) >= len(expected_conditions) and all(not boundary["compute_processes"] for boundary in isolation["boundaries"]),
        "independent_metric_recomputation": not calculation_failures,
        "memory_scope_valid": all(row["condition_process_peak_measured"] is False and row["condition_process_peak_allocated_bytes"] is None and row["condition_process_peak_reserved_bytes"] is None for row in successful_measured),
        "original_input_parity": bool(parity["original"]) and all(row["present_both"] and row["both_success"] and row["input_prompt_parity"] and row["input_token_parity"] for row in parity["original"]),
        "compressed_input_parity": bool(parity["compressed"]) and all(row["present_both"] and row["both_success"] and row["input_prompt_parity"] and row["input_token_parity"] for row in parity["compressed"]),
        "valid_quality_parsing": quality_contract_valid,
    }
    if dataset == "canonical_mock":
        gates["original_generated_token_parity"] = bool(parity["original"]) and all(
            row["generated_token_parity"] for row in parity["original"]
        )
        gates["canonical_mock_quality"] = bool(canonical_quality_rows) and all(
            row["quality"] and row["quality"]["quality_pass"] for row in canonical_quality_rows
        )
    elif dataset == "gsm8k":
        gates["original_generated_token_parity"] = bool(parity["original"]) and all(
            row["generated_token_parity"] for row in parity["original"]
        )
        gates["gsm8k_reference_valid"] = all(_normalize_numeric(str(row["reference_text"])) is not None for row in successful_measured)
        gates["compressed_numeric_answer_agreement"] = _parsed_agreement(
            measured[compressed_left], measured[compressed_right]
        )
        quality_mean = {
            condition: statistics.fmean(
                float(row["quality_score"])
                for row in measured[condition]
                if row["status"] == "success"
            )
            for condition in expected_conditions
        }
        gates["gsm8k_compressed_quality_non_regression"] = (
            quality_mean[compressed_left] >= quality_mean[original_left]
            and quality_mean[compressed_right] >= quality_mean[original_right]
        )
    elif dataset == "qmsum":
        gates["qmsum_outputs_nonempty"] = all(bool(str(row["decoded_output"]).strip()) for row in successful_measured)
        selections = [sample.get("context_selection") for sample in manifest["workload"]["samples"]]
        gates["qmsum_context_selection_accounting"] = all(
            isinstance(selection, dict)
            and selection.get("policy") == "query_aware_budgeted"
            and selection.get("selected_context_token_count", 0) <= selection.get("budget_tokens", 0)
            and bool(selection.get("selected_chunk_ids"))
            and len(selection.get("selected_chunk_ids", []))
            == len(selection.get("selected_source_ranges", []))
            and 0 <= selection.get("query_term_coverage", -1) <= 1
            and bool(selection.get("selected_context_sha256"))
            for selection in selections
        )
        gates["qmsum_selected_context_shared"] = all(
            len({
                row["selected_context_sha256"]
                for condition in expected_conditions
                for row in measured[condition]
                if row["sample_id"] == sample_id
            }) == 1
            for sample_id in manifest["workload"]["sample_ids"]
        )
        gates["qmsum_compressed_context_shared"] = all(
            len({
                row["compressed_context_sha256"]
                for condition in (compressed_left, compressed_right)
                for row in measured[condition]
                if row["sample_id"] == sample_id
            }) == 1
            for sample_id in manifest["workload"]["sample_ids"]
        )
    compressed_token_parity = bool(parity["compressed"]) and all(
        row["generated_token_parity"] for row in parity["compressed"]
    )
    meaningful_compression = bool(compressed_success) and all(
        row["target_user_token_reduction"] > 0 and row["target_full_token_reduction"] > 0
        for row in compressed_success
    )
    summaries: dict[str, Any] = {}
    for condition, rows in measured.items():
        success = [row for row in rows if row["status"] == "success"]
        summaries[condition] = {
            "condition": CONDITIONS[condition].name,
            "expected_row_count": manifest["expected_counts"]["per_condition_measured_rows"],
            "row_count": len(rows), "success_count": len(success), "failure_count": len(rows) - len(success),
            "generated_tokens": _describe([float(row["generated_token_count"]) for row in success]),
            "decode_tok_s": _describe([float(row["decode_tok_s"]) for row in success]),
            "generation_e2e_tok_s": _describe([float(row["generation_e2e_tok_s"]) for row in success]),
            "pipeline_e2e_tok_s": _describe([float(row["pipeline_e2e_tok_s"]) for row in success]),
            "generation_warm_e2e_time_ms": _describe([float(row["generation_warm_e2e_time_ms"]) for row in success]),
            "pipeline_warm_e2e_time_ms": _describe([float(row["pipeline_warm_e2e_time_ms"]) for row in success]),
            "generation_peak_allocated_bytes": max((int(row["generation_peak_allocated_bytes"]) for row in success), default=None),
            "generation_peak_reserved_bytes": max((int(row["generation_peak_reserved_bytes"]) for row in success), default=None),
            "condition_process_peak_allocated_bytes": None,
            "condition_process_peak_reserved_bytes": None,
            "mock_quality_pass_rate": statistics.fmean(float(row["quality"]["quality_pass"]) for row in success if row["quality"] is not None) if any(row["quality"] is not None for row in success) else None,
            "quality_score": _describe([float(row["quality_score"]) for row in success if row["quality_score"] is not None]),
            "parse_failure_count": sum(row["parser_status"] not in {"parsed", "not_applicable"} for row in success),
            "empty_output_count": sum(not bool(str(row["decoded_output"]).strip()) for row in success),
        }
        if condition in (original_right, compressed_right):
            summaries[condition].update(
                {
                    "draft_time_ms": _describe([float(row["draft_time_ms"]) for row in success]),
                    "verify_time_ms": _describe([float(row["verify_time_ms"]) for row in success]),
                    "drafted_tokens": sum(int(row["drafted_tokens"]) for row in success),
                    "accepted_tokens": sum(int(row["accepted_tokens"]) for row in success),
                    "tau": _describe([float(row["tau"]) for row in success]),
                }
            )
    c2_pipeline = summaries[original_right]["pipeline_warm_e2e_time_ms"]
    c4_pipeline = summaries[compressed_right]["pipeline_warm_e2e_time_ms"]
    c4_compressor = _describe([
        float(row["compressor_latency_ms"])
        for row in measured[compressed_right]
        if row["status"] == "success"
    ])
    c2_c4 = {
        "C2_generation_latency_ms": summaries[original_right]["generation_warm_e2e_time_ms"],
        "C4_generation_latency_ms": summaries[compressed_right]["generation_warm_e2e_time_ms"],
        "C4_compressor_latency_ms": c4_compressor,
        "C2_pipeline_e2e_ms": c2_pipeline,
        "C4_pipeline_e2e_ms": c4_pipeline,
        "C4_minus_C2_pipeline_e2e_mean_ms": (
            c4_pipeline["mean"] - c2_pipeline["mean"] if c2_pipeline and c4_pipeline else None
        ),
        "C2_decode_tok_s": summaries[original_right]["decode_tok_s"],
        "C4_decode_tok_s": summaries[compressed_right]["decode_tok_s"],
        "C2_pipeline_e2e_tok_s": summaries[original_right]["pipeline_e2e_tok_s"],
        "C4_pipeline_e2e_tok_s": summaries[compressed_right]["pipeline_e2e_tok_s"],
    }
    passed = all(gates.values())
    return {
        "schema": "ccdf.four-condition.audit.v2", "pass": passed,
        "conclusion": "PASS" if passed else "FAIL", "manifest_sha256": manifest["manifest_sha256"],
        "gates": gates, "conditions": summaries, "parity": parity,
        "architecture_comparisons": {"C2_vs_C4": c2_c4},
        "diagnostics": {
            "original_generated_token_parity": bool(parity["original"]) and all(
                row["generated_token_parity"] for row in parity["original"]
            ),
            "compressed_generated_token_parity": compressed_token_parity,
            "meaningful_compression": meaningful_compression,
            "meaningful_compression_status": "PASS" if meaningful_compression else "FAIL",
        },
        "dataset": dataset,
        "completeness": {"expected_count": len(expected_keys), "actual_count": len(actual_keys), "duplicates": duplicates, "missing": missing_keys, "unexpected": unexpected_keys, "schema_errors": schema_errors},
        "compression_integrity": {"duplicate_sample_ids": duplicate_cache_ids, "cache_order_match": cache_order_match, "hash_match": cache_hash_match},
        "independent_calculation_failures": calculation_failures,
        "error_summary": error_summary, "process_ids": process_ids, "compressor": compressor,
        "compression": {
            "policy": manifest["compression_policy"],
            "successful_compressions": sum(row["status"] == "success" and row["compression_applied"] for row in compression),
            "fallback_count": sum(row["status"] == "fallback" for row in compression),
            "fallback_rate": sum(row["status"] == "fallback" for row in compression) / len(compression),
            "compressor_original_tokens": _describe([float(row["compressor_original_tokens"]) for row in compression if row["status"] == "success" and row["compression_applied"]]),
            "compressor_compressed_tokens": _describe([float(row["compressor_compressed_tokens"]) for row in compression if row["status"] == "success" and row["compression_applied"]]),
            "compressor_token_keep_rate": _describe([float(row["compressor_token_keep_rate"]) for row in compression if row["status"] == "success" and row["compression_applied"]]),
            "target_user_original_tokens": _describe([float(row["target_user_original_tokens"]) for row in measured[compressed_left] if row["status"] == "success"]),
            "target_user_compressed_tokens": _describe([float(row["target_user_compressed_tokens"]) for row in measured[compressed_left] if row["status"] == "success"]),
            "target_user_keep_rate": _describe([float(row["target_user_keep_rate"]) for row in measured[compressed_left] if row["status"] == "success"]),
            "target_full_original_tokens": _describe([float(row["target_full_original_tokens"]) for row in measured[compressed_left] if row["status"] == "success"]),
            "target_full_compressed_tokens": _describe([float(row["target_full_compressed_tokens"]) for row in measured[compressed_left] if row["status"] == "success"]),
            "target_full_keep_rate": _describe([float(row["target_full_keep_rate"]) for row in measured[compressed_left] if row["status"] == "success"]),
            "compressor_latency_ms": _describe([float(row["compressor_latency_ms"]) for row in measured[compressed_left] if row["status"] == "success"]),
            "peak_allocated_bytes": max((int(row["compressor_peak_allocated_bytes"]) for row in measured[compressed_left] if row["status"] == "success"), default=None),
            "peak_reserved_bytes": max((int(row["compressor_peak_reserved_bytes"]) for row in measured[compressed_left] if row["status"] == "success"), default=None),
            "selection_keep_rate": _describe([float(row["selection_keep_rate"]) for row in compression if row.get("selection_keep_rate") is not None]),
            "llmlingua_keep_rate": _describe([float(row["llmlingua_keep_rate"]) for row in compression if row.get("llmlingua_keep_rate") is not None and row.get("compression_applied")]),
            "overall_keep_rate": _describe([float(row["overall_keep_rate"]) for row in compression if row.get("overall_keep_rate") is not None and row.get("compression_applied")]),
        },
        "quality_scope": (
            "Canonical mock quality validates protocol behavior only; no dataset quality is claimed."
            if dataset == "canonical_mock"
            else "GSM8K quality is anchored numeric exact match."
            if dataset == "gsm8k"
            else "QMSum quality is deterministic ROUGE-L F1 lexical overlap; semantic correctness is not claimed."
        ),
    }


def render_report(result: dict[str, Any]) -> str:
    lines = [
        "# Four-condition Stage 2 audit", "", f"Conclusion: **{result['conclusion']}**", "",
        result["quality_scope"], "", "## Gates", "", "| Gate | Result |", "|---|:---:|",
    ]
    lines.extend(f"| {name} | {'PASS' if passed else 'FAIL'} |" for name, passed in result["gates"].items())
    lines.extend(["", "## Diagnostics", "", "| Diagnostic | Result |", "|---|:---:|"])
    lines.extend(f"| {name} | {value} |" for name, value in result["diagnostics"].items())
    lines.extend(["", "## Condition metrics", "", "| ID | Condition | Success | Decode mean tok/s | Generation E2E mean tok/s | Pipeline E2E mean tok/s |", "|---|---|---:|---:|---:|---:|"])
    for condition, summary in result["conditions"].items():
        def mean(name: str) -> str:
            return f"{summary[name]['mean']:.4f}" if summary[name] else "N/A"
        lines.append(f"| {condition} | {summary['condition']} | {summary['success_count']}/{summary['expected_row_count']} | {mean('decode_tok_s')} | {mean('generation_e2e_tok_s')} | {mean('pipeline_e2e_tok_s')} |")
    return "\n".join(lines) + "\n"
