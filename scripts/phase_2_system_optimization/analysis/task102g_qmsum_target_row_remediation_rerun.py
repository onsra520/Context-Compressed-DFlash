from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any

TARGET_FIXTURE_IDS = (
    "qmsum_meeting_qa_test_0036",
    "qmsum_meeting_qa_test_0070",
    "qmsum_meeting_qa_test_0055",
    "qmsum_meeting_qa_test_0078",
    "qmsum_meeting_qa_test_0094",
    "qmsum_meeting_qa_test_0001",
)

DEFAULT_BASE_DIR = Path(
    "results/phase_2_system_optimization/final_reruns/"
    "task102g_qmsum_target_row_remediation_rerun"
)
DEFAULT_RUN_DIR = DEFAULT_BASE_DIR / "runs"
DEFAULT_OUTPUT_DIR = DEFAULT_BASE_DIR
DEFAULT_TARGET_DATASET = Path("data/eval/qmsum_meeting_qa_target_rows_task102f.jsonl")

OUTPUT_RELATIVE_PATHS = (
    Path("summary/task102g_remediation_run_summary.json"),
    Path("summary/task102g_target_row_outputs.jsonl"),
    Path("summary/task102g_run_metadata_audit.json"),
    Path("summary/task102g_next_task_decision.json"),
    Path("tables/task102g_runtime_table.csv"),
)

GENERATED_OUTPUT_LEAK_FIELDS = {
    "generated_text",
    "generated_answer",
    "model_answer",
    "model_output",
    "output",
    "prediction",
    "response",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_no} is not a JSON object")
        rows.append(payload)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _latest_run_artifact(run_dir: Path) -> Path | None:
    files = sorted(run_dir.glob("*_qmsum_target_rows_n6_mnt384.jsonl"))
    return files[-1] if files else None


def _fixture_id(row: dict[str, Any]) -> str:
    return str(row.get("fixture_id") or row.get("dataset_id") or row.get("id") or "")


def _number(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def _stats(values: list[float | None]) -> dict[str, float | None]:
    clean = [value for value in values if value is not None]
    if not clean:
        return {"avg": None, "min": None, "max": None}
    return {
        "avg": round(statistics.fmean(clean), 6),
        "min": round(min(clean), 6),
        "max": round(max(clean), 6),
    }


def _generated_text(row: dict[str, Any]) -> str:
    value = row.get("generated_text", "")
    return value if isinstance(value, str) else ""


def _looks_cap_limited(row: dict[str, Any]) -> bool:
    max_new_tokens = _number(row, "max_new_tokens")
    if not max_new_tokens:
        return False
    generated_tokens = _number(row, "generated_token_count", "output_tokens", "new_tokens")
    if generated_tokens is not None and generated_tokens >= max_new_tokens:
        return True
    text = _generated_text(row).strip()
    return bool(text) and not text.endswith((".", "?", "!", '"', "'", ")", "]"))


def _has_failure_flag(row: dict[str, Any]) -> bool:
    failure_keys = (
        "oom",
        "oom_flag",
        "cuda_failure",
        "cuda_error",
        "runtime_failure",
        "error",
        "failure",
    )
    for key in failure_keys:
        value = row.get(key)
        if value in (None, "", False, 0, "False", "false", "none", "None"):
            continue
        if value is not None:
            return True
    text = _generated_text(row).lower()
    return "cuda out of memory" in text or "runtimeerror: cuda" in text


def validate_target_dataset(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    errors: list[str] = []
    ids = [_fixture_id(row) for row in rows]
    expected = set(TARGET_FIXTURE_IDS)
    if len(rows) != 6:
        errors.append(f"expected 6 rows, found {len(rows)}")
    if set(ids) != expected:
        errors.append(f"fixture_ids mismatch: {sorted(set(ids))}")
    if len(set(ids)) != len(ids):
        errors.append("duplicate fixture_id found")
    for row in rows:
        fixture_id = _fixture_id(row) or "<missing-id>"
        missing = [
            field
            for field in ("id", "context", "question", "expected_answer", "prompt")
            if not str(row.get(field, "")).strip()
        ]
        if missing:
            errors.append(f"{fixture_id}: missing required fields {missing}")
        leaked = sorted(field for field in GENERATED_OUTPUT_LEAK_FIELDS if field in row)
        if leaked:
            errors.append(f"{fixture_id}: generated-output fields present {leaked}")
    return {
        "valid": not errors,
        "path": str(path),
        "row_count": len(rows),
        "fixture_ids": ids,
        "expected_fixture_ids": list(TARGET_FIXTURE_IDS),
        "errors": errors,
    }


def audit_run_metadata(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    ids = [_fixture_id(row) for row in rows]
    expected = set(TARGET_FIXTURE_IDS)
    if len(rows) != 6:
        errors.append(f"expected 6 result rows, found {len(rows)}")
    if set(ids) != expected:
        errors.append(f"fixture_ids mismatch: {sorted(set(ids))}")
    if len(set(ids)) != len(ids):
        errors.append("duplicate fixture_id found")
    for index, row in enumerate(rows, start=1):
        prefix = f"row {index} {_fixture_id(row) or '<missing-id>'}"
        if row.get("condition") != "CC-DFlash-R2":
            errors.append(f"{prefix}: condition={row.get('condition')!r}")
        if row.get("dataset_name") != "qmsum_meeting_qa_long":
            errors.append(f"{prefix}: dataset_name={row.get('dataset_name')!r}")
        if row.get("compressor_profile") != "light":
            errors.append(f"{prefix}: compressor_profile={row.get('compressor_profile')!r}")
        if row.get("compressor_device_map") != "cuda":
            errors.append(f"{prefix}: compressor_device_map={row.get('compressor_device_map')!r}")
        if row.get("requested_compressor_device_map") != "cuda":
            errors.append(f"{prefix}: requested_compressor_device_map={row.get('requested_compressor_device_map')!r}")
        if _boolish(row.get("local_files_only")) is not True:
            errors.append(f"{prefix}: local_files_only={row.get('local_files_only')!r}")
        if _boolish(row.get("qmsum_policy_suffix_override")) is not True:
            errors.append(f"{prefix}: qmsum_policy_suffix_override={row.get('qmsum_policy_suffix_override')!r}")
        if row.get("qmsum_answer_policy_type") != "qmsum_targeted_evidence_repair_v1":
            errors.append(f"{prefix}: qmsum_answer_policy_type={row.get('qmsum_answer_policy_type')!r}")
        if _boolish(row.get("qmsum_answer_policy_preserved")) is not True:
            errors.append(f"{prefix}: qmsum_answer_policy_preserved={row.get('qmsum_answer_policy_preserved')!r}")
        if not _generated_text(row).strip():
            errors.append(f"{prefix}: empty generated_text")
        if _has_failure_flag(row):
            errors.append(f"{prefix}: OOM/CUDA/runtime failure flag detected")
    return {
        "valid": not errors,
        "row_count": len(rows),
        "fixture_ids": ids,
        "expected_fixture_ids": list(TARGET_FIXTURE_IDS),
        "metadata_confirmed": not errors,
        "compressor_profile_values": sorted({str(row.get("compressor_profile")) for row in rows}),
        "compressor_device_map_values": sorted({str(row.get("compressor_device_map")) for row in rows}),
        "requested_compressor_device_map_values": sorted({str(row.get("requested_compressor_device_map")) for row in rows}),
        "local_files_only_values": sorted({str(_boolish(row.get("local_files_only"))) for row in rows}),
        "policy_type_values": sorted({str(row.get("qmsum_answer_policy_type")) for row in rows}),
        "policy_suffix_override_values": sorted({str(_boolish(row.get("qmsum_policy_suffix_override"))) for row in rows}),
        "oom_cuda_failure_flags": any(_has_failure_flag(row) for row in rows),
        "empty_or_malformed_outputs": sum(1 for row in rows if not _generated_text(row).strip()),
        "errors": errors,
    }


def summarize_run(rows: list[dict[str, Any]], *, run_artifact: Path, dataset_audit: dict[str, Any], metadata_audit: dict[str, Any]) -> dict[str, Any]:
    cap_limited = [row for row in rows if _looks_cap_limited(row)]
    summary = {
        "task": "T102G — QMSum Target-row Remediation Rerun",
        "decision": "PASS_WITH_CAVEAT" if dataset_audit["valid"] and metadata_audit["valid"] else "PARTIAL",
        "run_artifact": str(run_artifact),
        "row_count": len(rows),
        "expected_row_count": 6,
        "fixture_id_match": set(metadata_audit["fixture_ids"]) == set(TARGET_FIXTURE_IDS),
        "target_dataset_valid": dataset_audit["valid"],
        "metadata_valid": metadata_audit["valid"],
        "empty_or_malformed_count": metadata_audit["empty_or_malformed_outputs"],
        "cap_limited_incomplete_heuristic_count": len(cap_limited),
        "oom_cuda_failure_flags": metadata_audit["oom_cuda_failure_flags"],
        "metrics": {
            "t_compress_ms": _stats([_number(row, "t_compress_ms") for row in rows]),
            "e2e_time_s": _stats([_number(row, "generation_time_s", "e2e_time_s") for row in rows]),
            "tokens_per_second": _stats([_number(row, "tok_per_sec", "tokens_per_second") for row in rows]),
            "R_actual": _stats([_number(row, "R_actual") for row in rows]),
            "tau_mean": _stats([_number(row, "tau_mean") for row in rows]),
            "t_prefill_ms": _stats([_number(row, "t_prefill_ms") for row in rows]),
            "vram_allocated_gib": _stats([_number(row, "vram_allocated_gib") for row in rows]),
            "vram_reserved_gib": _stats([_number(row, "vram_reserved_gib") for row in rows]),
        },
        "scope": {
            "condition": "CC-DFlash-R2",
            "dataset": "qmsum_meeting_qa_long",
            "n": 6,
            "seed": 42,
            "max_new_tokens": 384,
            "compressor_profile": "light",
            "compressor_device_map": "cuda",
            "no_qmsum_n100": True,
            "no_full_matrix": True,
            "no_llm_judge": True,
            "semantic_reassessment_deferred_to": "T102H",
        },
    }
    return summary


def build_target_row_outputs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "fixture_id": _fixture_id(row),
            "prompt_id": row.get("prompt_id"),
            "expected_answer": row.get("expected_answer"),
            "generated_text": row.get("generated_text"),
            "generated_token_count": row.get("generated_token_count", row.get("output_tokens")),
            "output_tokens": row.get("output_tokens"),
            "max_new_tokens": row.get("max_new_tokens"),
            "t_compress_ms": row.get("t_compress_ms"),
            "generation_time_s": row.get("generation_time_s"),
            "tokens_per_second": row.get("tokens_per_second", row.get("tok_per_sec")),
            "R_actual": row.get("R_actual"),
            "tau_mean": row.get("tau_mean"),
            "vram_reserved_gib": row.get("vram_reserved_gib"),
        }
        for row in rows
    ]


def write_runtime_table(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "fixture_id",
        "prompt_id",
        "output_tokens",
        "generated_token_count",
        "t_compress_ms",
        "generation_time_s",
        "tokens_per_second",
        "R_actual",
        "tau_mean",
        "t_prefill_ms",
        "vram_allocated_gib",
        "vram_reserved_gib",
        "cap_limited_incomplete_heuristic",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "fixture_id": _fixture_id(row),
                    "prompt_id": row.get("prompt_id"),
                    "output_tokens": row.get("output_tokens"),
                    "generated_token_count": row.get("generated_token_count"),
                    "t_compress_ms": row.get("t_compress_ms"),
                    "generation_time_s": row.get("generation_time_s"),
                    "tokens_per_second": row.get("tokens_per_second", row.get("tok_per_sec")),
                    "R_actual": row.get("R_actual"),
                    "tau_mean": row.get("tau_mean"),
                    "t_prefill_ms": row.get("t_prefill_ms"),
                    "vram_allocated_gib": row.get("vram_allocated_gib"),
                    "vram_reserved_gib": row.get("vram_reserved_gib"),
                    "cap_limited_incomplete_heuristic": _looks_cap_limited(row),
                }
            )


def build_next_task_decision(summary: dict[str, Any]) -> dict[str, Any]:
    if (
        summary["row_count"] == 6
        and summary["fixture_id_match"]
        and summary["target_dataset_valid"]
        and summary["metadata_valid"]
        and summary["empty_or_malformed_count"] == 0
        and not summary["oom_cuda_failure_flags"]
    ):
        return {
            "decision": "PROCEED_TO_T102H",
            "next_task": "T102H — QMSum Remediation Reassessment",
            "reason": "Target-row rerun completed 6/6 with correct light/cuda/policy metadata and needs before/after deterministic quality reassessment.",
            "blocked": [],
        }
    return {
        "decision": "RETURN_TO_T102A",
        "next_task": "T102A — QMSum Failure Audit / Fix",
        "reason": "Target-row rerun infrastructure, metadata, or artifact integrity failed a T102G gate.",
        "blocked": [
            "Do not proceed to T102H until row count, target IDs, policy metadata, CUDA metadata, and output integrity are valid."
        ],
    }


def analyze(
    *,
    run_artifact: Path | None = None,
    target_dataset: Path = DEFAULT_TARGET_DATASET,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    selected_run = run_artifact or _latest_run_artifact(DEFAULT_RUN_DIR)
    if selected_run is None:
        raise FileNotFoundError(f"No T102G run artifact found in {DEFAULT_RUN_DIR}")
    rows = read_jsonl(selected_run)
    dataset_audit = validate_target_dataset(target_dataset)
    metadata_audit = audit_run_metadata(rows)
    summary = summarize_run(rows, run_artifact=selected_run, dataset_audit=dataset_audit, metadata_audit=metadata_audit)
    next_task_decision = build_next_task_decision(summary)

    write_json(output_dir / "summary/task102g_remediation_run_summary.json", summary)
    write_jsonl(output_dir / "summary/task102g_target_row_outputs.jsonl", build_target_row_outputs(rows))
    write_json(
        output_dir / "summary/task102g_run_metadata_audit.json",
        {
            "target_dataset_audit": dataset_audit,
            "run_metadata_audit": metadata_audit,
        },
    )
    write_json(output_dir / "summary/task102g_next_task_decision.json", next_task_decision)
    write_runtime_table(output_dir / "tables/task102g_runtime_table.csv", rows)

    return {
        "decision": summary["decision"],
        "summary": summary,
        "metadata_audit": metadata_audit,
        "target_dataset_audit": dataset_audit,
        "next_task_decision": next_task_decision,
        "output_dir": str(output_dir),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Task102G QMSum target-row remediation rerun artifacts.")
    parser.add_argument("--run-artifact", type=Path, default=None, help="T102G run JSONL. Defaults to latest target-row run.")
    parser.add_argument("--target-dataset", type=Path, default=DEFAULT_TARGET_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = analyze(run_artifact=args.run_artifact, target_dataset=args.target_dataset, output_dir=args.output_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
