"""Authoritative run manifest for four-condition evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from ...config import Rec2Config
from .conditions import CONDITIONS

SCHEMA = "ccdf.four-condition.manifest.v3"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _model_identity(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        key: profile.get(key)
        for key in ("model_id", "local_path", "quantization", "dtype")
        if key in profile
    }


def build_run_manifest(
    config: Rec2Config,
    samples: list[dict[str, Any]],
    *,
    run_id: str,
    repetitions: int,
    warmups: int,
    max_new_tokens: int,
    requested_keep_rate: float | None,
    workload_name: str,
) -> dict[str, Any]:
    if not run_id or not workload_name:
        raise ValueError("run_id and workload_name must be non-empty")
    if not samples or repetitions < 1 or warmups < 0:
        raise ValueError("manifest requires samples, positive repetitions, and non-negative warmups")
    sample_ids = [str(sample["sample_id"]) for sample in samples]
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("manifest samples contain duplicate sample IDs")
    sample_entries = [
        {
            "dataset": str(sample["dataset"]),
            "split": str(sample["split"]),
            "sample_id": str(sample["sample_id"]),
            "prompt_sha256": _text_sha256(str(sample["prompt"])),
            "task_type": sample.get("task_type"),
            "source_fingerprint": sample.get("source_fingerprint"),
            "prompt_version": sample.get("prompt_version"),
            "context_selection": sample.get("metadata", {}).get("context_selection"),
        }
        for sample in samples
    ]
    expected_records: list[dict[str, Any]] = []
    for condition_id in CONDITIONS:
        request_index = 0
        for warmup_index in range(warmups):
            expected_records.append(
                {
                    "condition_id": condition_id,
                    "sample_id": sample_ids[warmup_index % len(sample_ids)],
                    "phase": "warmup",
                    "repetition": None,
                    "request_index": request_index,
                }
            )
            request_index += 1
        for repetition in range(repetitions):
            for sample_id in sample_ids:
                expected_records.append(
                    {
                        "condition_id": condition_id,
                        "sample_id": sample_id,
                        "phase": "measured",
                        "repetition": repetition,
                        "request_index": request_index,
                    }
                )
                request_index += 1
    policy = {
        "runtime": {
            key: config.get(f"runtime.{key}")
            for key in (
                "seed",
                "temperature",
                "attention_backend",
                "sdpa_kernel",
                "enable_thinking",
                "stop_token_ids",
            )
        },
        "optimization": config.require("optimization"),
        "max_new_tokens": max_new_tokens,
    }
    compressor_profile = dict(config.require("models.compressor"))
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "workload": {
            "name": workload_name,
            "samples": sample_entries,
            "sample_ids": sample_ids,
        },
        "conditions": [
            {
                "condition_id": condition.condition_id,
                "name": condition.name,
                "runtime_condition": condition.runtime_condition,
                "prompt_kind": condition.prompt_kind,
            }
            for condition in CONDITIONS.values()
        ],
        "repetitions": repetitions,
        "warmups": warmups,
        "seed": int(config.require("runtime.seed")),
        "max_new_tokens": max_new_tokens,
        "requested_keep_rate": requested_keep_rate,
        "compression_policy": (
            {"mode": "fixed", "keep_rate": requested_keep_rate}
            if requested_keep_rate is not None
            else {
                "mode": "adaptive_target_user_tokens",
                **dict(config.require("dataset_smoke.compression.adaptive_keep_rate")),
            }
        ),
        "policy_sha256": _sha256(policy),
        "policy": policy,
        "config_sha256": _file_sha256(config.path),
        "models": {
            "baseline": _model_identity(dict(config.require("models.baseline"))),
            "dflash_target": _model_identity(dict(config.require("models.dflash.target"))),
            "dflash_drafter": _model_identity(dict(config.require("models.dflash.drafter"))),
        },
        "compressor": {
            **_model_identity(compressor_profile),
            "reserved_budget_gib": float(compressor_profile["reserved_budget_gib"]),
        },
        "expected_records": expected_records,
        "expected_counts": {
            "compression_rows": len(samples),
            "per_condition_warmup_rows": warmups,
            "per_condition_measured_rows": repetitions * len(samples),
            "raw_rows_total": len(expected_records),
        },
    }
    payload["manifest_sha256"] = _sha256(payload)
    validate_manifest(payload)
    return payload


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != SCHEMA:
        raise ValueError("unexpected run manifest schema")
    supplied = manifest.get("manifest_sha256")
    content = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if supplied != _sha256(content):
        raise ValueError("run manifest hash mismatch")
    samples = manifest["workload"]["samples"]
    sample_ids = [row["sample_id"] for row in samples]
    if sample_ids != manifest["workload"]["sample_ids"] or len(sample_ids) != len(set(sample_ids)):
        raise ValueError("run manifest sample order/uniqueness mismatch")
    condition_ids = [row["condition_id"] for row in manifest["conditions"]]
    if condition_ids != list(CONDITIONS):
        raise ValueError("run manifest condition contract mismatch")
    keys = [expected_key(row) for row in manifest["expected_records"]]
    if len(keys) != len(set(keys)):
        raise ValueError("run manifest contains duplicate expected record keys")
    counts = manifest["expected_counts"]
    if counts["compression_rows"] != len(samples):
        raise ValueError("run manifest compression count mismatch")
    if counts["raw_rows_total"] != len(keys):
        raise ValueError("run manifest raw count mismatch")


def expected_key(row: dict[str, Any]) -> tuple[str, str, str, int | None, int]:
    return (
        str(row["condition_id"]),
        str(row["sample_id"]),
        str(row["phase"]),
        row["repetition"],
        int(row["request_index"]),
    )


def manifest_sample_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    validate_manifest(manifest)
    return {row["sample_id"]: row for row in manifest["workload"]["samples"]}


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    validate_manifest(manifest)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
