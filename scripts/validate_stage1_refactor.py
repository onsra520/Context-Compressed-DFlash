#!/usr/bin/env python3
"""Independently recompute the Stage 1 refactor regression contract."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import statistics
import tarfile
from collections import Counter
from pathlib import Path
from typing import Any


TRUTH_METRICS = {
    "baseline_decode_mean": 30.963077384807953,
    "dflash_decode_mean": 101.00723894286574,
    "dflash_decode_median": 109.34236902681347,
    "dflash_peak_reserved_gib": 3.626953125,
}
REQUIRED_GATES = (
    "generated_token_parity",
    "quality",
    "structural",
    "memory",
    "policy",
    "metric_validity",
    "workload",
)
TIMING_FIELDS = (
    "prompt_prepare_ms",
    "target_prefill_ms",
    "decode_total_ms",
    "generation_total_ms",
    "warm_request_ms",
)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _rows(path: Path) -> tuple[bytes, list[dict[str, Any]]]:
    raw = path.read_bytes()
    return raw, [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]


def _tar_member(archive: Path, name: str) -> bytes:
    with tarfile.open(archive, "r:gz") as handle:
        extracted = handle.extractfile(name)
        if extracted is None:
            raise FileNotFoundError(f"archive member not found: {name}")
        return extracted.read()


def _describe(values: list[float]) -> dict[str, float | int]:
    if not values or any(not math.isfinite(value) for value in values):
        raise ValueError("metric series must contain finite values")
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def _schema_fingerprint(row: dict[str, Any]) -> dict[str, list[str]]:
    nested = {"row": sorted(row)}
    for key in ("contract", "quality", "timing", "memory", "metrics", "model", "runtime"):
        value = row.get(key)
        nested[key] = sorted(value) if isinstance(value, dict) else []
    dflash = row.get("dflash")
    nested["dflash"] = sorted(dflash) if isinstance(dflash, dict) else []
    return nested


def _normalized_ast(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    protocol = ast.Module(
        body=[node for node in tree.body if isinstance(node, (ast.Assign, ast.FunctionDef))],
        type_ignores=[],
    )
    return _sha256(ast.dump(protocol, include_attributes=False).encode("utf-8"))


def validate(args: argparse.Namespace) -> dict[str, Any]:
    baseline_raw, baseline_rows = _rows(args.baseline)
    dflash_raw, dflash_rows = _rows(args.dflash)
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    truth_baseline_raw = _tar_member(args.truth_archive, "./baseline-raw.jsonl")
    truth_dflash_raw = _tar_member(args.truth_archive, "./dflash-raw.jsonl")
    truth_baseline = [json.loads(line) for line in truth_baseline_raw.decode().splitlines() if line.strip()]
    truth_dflash = [json.loads(line) for line in truth_dflash_raw.decode().splitlines() if line.strip()]

    baseline_measured = [row for row in baseline_rows if row["phase"] == "measured"]
    dflash_measured = [row for row in dflash_rows if row["phase"] == "measured"]
    baseline_by_key = {(row["prompt_id"], row["repetition"]): row for row in baseline_measured}
    dflash_by_key = {(row["prompt_id"], row["repetition"]): row for row in dflash_measured}
    keys = sorted(set(baseline_by_key) | set(dflash_by_key))
    parity = {
        f"{prompt_id}:{repetition}": bool(
            (left := baseline_by_key.get((prompt_id, repetition)))
            and (right := dflash_by_key.get((prompt_id, repetition)))
            and left["generated_token_ids"] == right["generated_token_ids"]
        )
        for prompt_id, repetition in keys
    }
    contract_parity = all(
        baseline_by_key[key]["contract"] == dflash_by_key[key]["contract"]
        for key in set(baseline_by_key) & set(dflash_by_key)
    )
    timing_valid = all(
        math.isfinite(float(row["timing"][field])) and float(row["timing"][field]) > 0
        for row in baseline_measured + dflash_measured
        for field in TIMING_FIELDS
    )
    structural = all(
        not row["runtime"]["output_health"]["empty"]
        and not row["runtime"]["output_health"]["repetition_detected"]
        for row in baseline_measured + dflash_measured
    ) and all(
        all(item["structural_pass"] for item in row["dflash"]["structural_audit"])
        for row in dflash_measured
    )
    phases = {
        "baseline": dict(Counter(row["phase"] for row in baseline_rows)),
        "dflash": dict(Counter(row["phase"] for row in dflash_rows)),
    }
    workload = (
        len(baseline_rows) == len(dflash_rows) == 51
        and phases["baseline"] == phases["dflash"] == {"warmup": 1, "measured": 50}
        and len(keys) == 50
        and len({row["prompt_id"] for row in baseline_measured}) == 10
    )
    independently_computed_gates = {
        "generated_token_parity": bool(parity) and all(parity.values()),
        "quality": all(
            row["quality"]["quality_pass"] for row in baseline_measured + dflash_measured
        ),
        "structural": structural,
        "memory": all(row["memory"].get("gate_pass") is not False for row in dflash_rows),
        "policy": contract_parity,
        "metric_validity": timing_valid,
        "workload": workload,
    }
    baseline_decode = _describe(
        [float(row["metrics"]["decode_tok_s"]) for row in baseline_measured]
    )
    dflash_decode = _describe(
        [float(row["metrics"]["decode_tok_s"]) for row in dflash_measured]
    )
    peak_reserved = max(float(row["memory"]["peak_reserved_bytes"]) for row in dflash_rows) / 1024**3
    performance = {
        "baseline_decode_mean": baseline_decode["mean"],
        "baseline_mean_delta_percent": (
            baseline_decode["mean"] / TRUTH_METRICS["baseline_decode_mean"] - 1
        )
        * 100,
        "dflash_decode_mean": dflash_decode["mean"],
        "dflash_mean_delta_percent": (
            dflash_decode["mean"] / TRUTH_METRICS["dflash_decode_mean"] - 1
        )
        * 100,
        "dflash_decode_median": dflash_decode["median"],
        "dflash_median_delta_percent": (
            dflash_decode["median"] / TRUTH_METRICS["dflash_decode_median"] - 1
        )
        * 100,
        "dflash_peak_reserved_gib": peak_reserved,
        "dflash_peak_delta_gib": peak_reserved - TRUTH_METRICS["dflash_peak_reserved_gib"],
    }
    current_schema = {
        "baseline": _schema_fingerprint(baseline_rows[0]),
        "dflash": _schema_fingerprint(dflash_rows[0]),
    }
    truth_schema = {
        "baseline": _schema_fingerprint(truth_baseline[0]),
        "dflash": _schema_fingerprint(truth_dflash[0]),
    }
    required_pass = all(independently_computed_gates.values())
    mock08 = [value for key, value in parity.items() if key.startswith("mock-08:")]
    reported_required = {name: summary["gates"][name] for name in REQUIRED_GATES}
    checks = {
        "required_gates_recomputed_pass": required_pass,
        "reported_required_gates_match": reported_required == independently_computed_gates,
        "parity_50_of_50": sum(parity.values()) == len(parity) == 50,
        "mock08_5_of_5": sum(mock08) == len(mock08) == 5,
        "schema_matches_correctness_truth": current_schema == truth_schema,
        "baseline_summary_matches": math.isclose(
            float(summary["conditions"]["baseline"]["throughput_tok_s"]["decode_tok_s"]["mean"]),
            float(baseline_decode["mean"]),
            rel_tol=1e-12,
        ),
        "dflash_summary_matches": math.isclose(
            float(summary["conditions"]["dflash"]["throughput_tok_s"]["decode_tok_s"]["mean"]),
            float(dflash_decode["mean"]),
            rel_tol=1e-12,
        ),
        "no_decode_tok_s_drop_over_5_percent": performance["baseline_mean_delta_percent"] >= -5
        and performance["dflash_mean_delta_percent"] >= -5,
    }
    if args.current_protocol_source and args.truth_protocol_source:
        checks["normalized_protocol_ast_matches_truth"] = _normalized_ast(
            args.current_protocol_source
        ) == _normalized_ast(args.truth_protocol_source)
    return {
        "schema": "ccdf.source-refactor.independent-validation.v1",
        "pass": all(checks.values()),
        "stage1_required_gate_conclusion": "PASS" if required_pass else "FAIL",
        "legacy_full_summary_conclusion": summary["conclusion"],
        "legacy_extra_performance_gate": summary["gates"][
            "workload_performance_rec2_equivalence"
        ],
        "checks": checks,
        "independently_computed_gates": independently_computed_gates,
        "reported_required_gates": reported_required,
        "counts": {"phases": phases, "parity_pass": sum(parity.values()), "parity_total": len(parity)},
        "mock08": {"pass": sum(mock08), "total": len(mock08)},
        "performance_vs_correctness_truth": performance,
        "independent_metrics": {"baseline_decode_tok_s": baseline_decode, "dflash_decode_tok_s": dflash_decode},
        "raw_identity": {
            "current_baseline_sha256": _sha256(baseline_raw),
            "current_dflash_sha256": _sha256(dflash_raw),
            "truth_baseline_sha256": _sha256(truth_baseline_raw),
            "truth_dflash_sha256": _sha256(truth_dflash_raw),
        },
        "schema_fingerprint": current_schema,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--dflash", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--truth-archive", type=Path, required=True)
    parser.add_argument("--current-protocol-source", type=Path)
    parser.add_argument("--truth-protocol-source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = validate(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pass": result["pass"], "checks": result["checks"]}, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
