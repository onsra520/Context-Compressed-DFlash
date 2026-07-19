#!/usr/bin/env python3
"""Validate and summarize the Stage 2 freeze through QMSum n=10 evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


REVIEW_ROOT = Path("docs/reviews/9-stage2-freeze-to-qmsum-n10-audit")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parity_count(audit: dict[str, Any], key: str) -> tuple[int, int]:
    rows = audit["parity"][key]
    return sum(bool(row["generated_token_parity"]) for row in rows), len(rows)


def _stage(name: str) -> dict[str, Any]:
    path = REVIEW_ROOT / name / "metrics" / "audit.json"
    audit = _load(path)
    original = _parity_count(audit, "original")
    compressed = _parity_count(audit, "compressed")
    return {
        "name": name,
        "audit_path": str(path.relative_to(REVIEW_ROOT)),
        "audit_sha256": _sha256(path),
        "pass": bool(audit["pass"]),
        "failed_gates": [key for key, value in audit["gates"].items() if not value],
        "condition_success": {
            condition: {
                "success": details["success_count"],
                "expected": details["expected_row_count"],
            }
            for condition, details in audit["conditions"].items()
        },
        "original_generated_token_parity": {"pass": original[0], "total": original[1]},
        "compressed_generated_token_parity": {"pass": compressed[0], "total": compressed[1]},
        "meaningful_compression": audit["diagnostics"]["meaningful_compression"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    canonical_path = REVIEW_ROOT / "canonical" / "metrics" / "stage3-guard-audit.json"
    pipeline_path = REVIEW_ROOT / "dataset" / "pipeline-audit.json"
    canonical = _load(canonical_path)
    pipeline = _load(pipeline_path)
    stages = {name: _stage(name) for name in ("mock", "gsm8k", "qmsum")}

    checks = {
        "canonical_guard_all_hard_gates": all(canonical["hard_gates"].values()),
        "dataset_pipeline": bool(pipeline["pass"]),
        "raw_source_hashes_unchanged": (
            pipeline["raw_sha256_before"] == pipeline["raw_sha256_after"]
        ),
        "mock_all_hard_gates": stages["mock"]["pass"],
        "gsm8k_all_hard_gates": stages["gsm8k"]["pass"],
        "qmsum_only_expected_hard_failure": (
            not stages["qmsum"]["pass"]
            and stages["qmsum"]["failed_gates"] == ["original_generated_token_parity"]
        ),
        "qmsum_all_conditions_complete": all(
            value["success"] == value["expected"]
            for value in stages["qmsum"]["condition_success"].values()
        ),
        "qmsum_meaningful_compression": stages["qmsum"]["meaningful_compression"],
        "full_benchmark_not_executed": not Path("results").exists(),
    }
    evidence_valid = all(checks.values())
    decision = "NOT_READY_FOR_FULL_BENCHMARK" if evidence_valid else "INVALID_EVIDENCE"
    payload = {
        "schema": "ccdf.stage3-final-self-audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review_root": str(REVIEW_ROOT),
        "checks": checks,
        "evidence_valid": evidence_valid,
        "decision": decision,
        "blocking_gate": {
            "dataset": "qmsum",
            "gate": "original_generated_token_parity",
            "observed": stages["qmsum"]["original_generated_token_parity"],
            "required": {"pass": 10, "total": 10},
        },
        "stages": stages,
        "source_evidence": {
            "canonical_guard": {
                "path": str(canonical_path.relative_to(REVIEW_ROOT)),
                "sha256": _sha256(canonical_path),
            },
            "dataset_pipeline": {
                "path": str(pipeline_path.relative_to(REVIEW_ROOT)),
                "sha256": _sha256(pipeline_path),
            },
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"decision": decision, "evidence_valid": evidence_valid}, sort_keys=True))
    return 0 if evidence_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
