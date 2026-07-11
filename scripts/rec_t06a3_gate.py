#!/usr/bin/env python3
"""Evaluate the coupled Rec-T06A3 validation gate without loading models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ccdf.artifacts.writer import write_json
from ccdf.datasets.io import read_jsonl


def read_rows(directory: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((directory / "runs").glob("*.jsonl")):
        rows.extend(read_jsonl(path))
    if not rows:
        raise FileNotFoundError(f"no run rows found under {directory / 'runs'}")
    return rows


def structural_checks(rows: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    savings_seen = False
    for row in rows:
        condition = row["condition"]["condition_id"]
        if condition == "baseline-ar":
            continue
        label = f"{row['dataset']}/{condition}/{row['fixture_id']}"
        if row["verification_calls"] != row["target_block_verification_calls"]:
            failures.append(f"{label}: verification call mismatch")
        if row["target_single_token_fallback_calls"] != 0:
            failures.append(f"{label}: single-token target fallback used")
        if row["target_hidden_refresh_calls"] != 0:
            failures.append(f"{label}: target hidden refresh used")
        expected_calls = row["target_prefill_calls"] + row["target_block_verification_calls"]
        if row["total_target_forward_calls"] != expected_calls:
            failures.append(f"{label}: hidden target forward call")
        expected_output = row["target_seed_tokens"] + sum(row["emitted_acceptance_lengths"])
        if row["output_tokens"] != expected_output:
            failures.append(f"{label}: seed-aware output accounting mismatch")
        if not all(block.get("structural_pass") for block in row["structural_audit"]):
            failures.append(f"{label}: structural verifier failure")
        if row["total_target_forward_calls"] < row["output_tokens"]:
            savings_seen = True
    if not savings_seen:
        failures.append("no DFlash row demonstrated fewer target forwards than emitted tokens")
    return failures


def condition_rows(rows: list[dict[str, Any]], condition: str) -> list[dict[str, Any]]:
    return [row for row in rows if row["condition"]["condition_id"] == condition]


def health_count(rows: list[dict[str, Any]], key: str) -> int:
    return sum(bool(row.get(key)) for row in rows)


def evaluate(root: Path, stage: str) -> dict[str, Any]:
    gsm = read_rows(root / stage / "gsm8k")
    qms = read_rows(root / stage / "qmsum")
    failures = structural_checks(gsm + qms)

    for dataset, rows in (("gsm8k", gsm), ("qmsum", qms)):
        if health_count(rows, "repetition_detected"):
            failures.append(f"{dataset}: repetition detected")
        if health_count(rows, "instruction_echo_detected"):
            failures.append(f"{dataset}: instruction echo detected")
        if any(not row.get("success") for row in rows):
            failures.append(f"{dataset}: runtime failure present")

    gsm_baseline = condition_rows(gsm, "baseline-ar")
    gsm_dflash = condition_rows(gsm, "dflash-r1")
    qms_baseline = condition_rows(qms, "baseline-ar")
    qms_dflash = condition_rows(qms, "dflash-r1")
    if not all((gsm_baseline, gsm_dflash, qms_baseline, qms_dflash)):
        failures.append("baseline-ar and dflash-r1 rows are required for both datasets")

    if health_count(gsm_baseline + gsm_dflash, "cap_hit") != 0:
        failures.append("gsm8k: cap hits must be zero")
    if any(not row.get("output_contract_hit") for row in gsm_baseline + gsm_dflash):
        failures.append("gsm8k: every Baseline/DFlash row must complete the final-answer contract")

    qms_cap_limit = 1 if stage == "n10" else 0
    for condition, selected in (("baseline-ar", qms_baseline), ("dflash-r1", qms_dflash)):
        if health_count(selected, "cap_hit") > qms_cap_limit:
            failures.append(
                f"qmsum/{condition}: more than {qms_cap_limit} cap hit"
            )

    baseline_strict = sum(row["quality"].get("label") == "strict_correct" for row in gsm_baseline)
    dflash_strict = sum(row["quality"].get("label") == "strict_correct" for row in gsm_dflash)
    if dflash_strict < baseline_strict - 1:
        failures.append(
            f"gsm8k: DFlash strict correctness regressed by more than one "
            f"({baseline_strict} vs {dflash_strict})"
        )

    exact_matches = 0
    paired = 0
    baseline_by_fixture = {row["fixture_id"]: row for row in qms_baseline + gsm_baseline}
    for row in qms_dflash + gsm_dflash:
        baseline = baseline_by_fixture.get(row["fixture_id"])
        if baseline is None:
            continue
        paired += 1
        exact_matches += baseline["generated_token_ids_hash"] == row["generated_token_ids_hash"]

    decision = {
        "task_id": "Rec-T06A3",
        "stage": stage,
        "status": "PASS" if not failures else "BLOCKED",
        "claim_boundary": {
            "exact_cached_ar_token_equivalence": "NOT_CLAIMED",
            "target_verified_block_decoding": "REQUIRED_AND_AUDITED",
            "quality_preservation_vs_baseline": "EMPIRICALLY_EVALUATED",
        },
        "gsm8k": {
            "baseline_rows": len(gsm_baseline),
            "dflash_rows": len(gsm_dflash),
            "baseline_strict_correct": baseline_strict,
            "dflash_strict_correct": dflash_strict,
            "cap_hits": health_count(gsm_baseline + gsm_dflash, "cap_hit"),
        },
        "qmsum": {
            "baseline_rows": len(qms_baseline),
            "dflash_rows": len(qms_dflash),
            "semantic_correctness": "NOT_CLAIMED",
            "cap_hits": health_count(qms_baseline + qms_dflash, "cap_hit"),
        },
        "exact_token_match_rate_observed_not_claimed": exact_matches / paired if paired else None,
        "failures": failures,
    }
    write_json(root / stage / "gate_decision.json", decision)
    return decision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["n3", "n10"], required=True)
    parser.add_argument("--root", default="results/Rec-T06A3")
    args = parser.parse_args()
    decision = evaluate(Path(args.root), args.stage)
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0 if decision["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
