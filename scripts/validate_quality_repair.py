#!/usr/bin/env python3
"""Independent final consistency checks for the quality-repair evidence pack."""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "docs/reviews/10-quality-repair-gsm8k-qmsum-n10"


def read(path: str) -> dict:
    return json.loads((PACK / path).read_text(encoding="utf-8"))


def main() -> int:
    mock = read("mock/metrics/audit.json")
    gsm = read("gsm8k/metrics/audit.json")
    qms = read("qmsum/metrics/audit.json")
    pipeline = read("dataset/pipeline-audit.json")
    fallback = read("fallback-summary.json")
    parity = read("qmsum/metrics/parity-diagnostics.json")
    canonical = read("canonical/stage3-guard-audit.json")
    checks = {
        "three_workload_audits_pass": all(row["pass"] for row in (mock, gsm, qms)),
        "all_measured_rows_complete": all(
            row["completeness"]["actual_count"] == row["completeness"]["expected_count"] == 44
            for row in (mock, gsm, qms)
        ),
        "mock_quality_10_of_10_each": all(
            row["quality_score"]["mean"] == 1.0 for row in mock["conditions"].values()
        ),
        "gsm_em_equal_point_five_each": all(
            row["quality_score"]["mean"] == 0.5 for row in gsm["conditions"].values()
        ),
        "gsm_non_regression_gate": gsm["gates"]["gsm8k_compressed_quality_non_regression"],
        "qmsum_no_empty_outputs": qms["gates"]["qmsum_outputs_nonempty"],
        "qmsum_selector_gates": all(
            qms["gates"][name]
            for name in (
                "qmsum_context_selection_accounting",
                "qmsum_selected_context_shared",
                "qmsum_compressed_context_shared",
            )
        ),
        "raw_inputs_immutable": pipeline["raw_immutable"],
        "zero_fallbacks": fallback["total_fallbacks"] == 0,
        "qmsum_parity_diagnostics_retained": len(parity["original"]) == len(parity["compressed"]) == 2,
        "c2_c4_delta_recomputed": math.isclose(
            qms["architecture_comparisons"]["C2_vs_C4"]["C4_minus_C2_pipeline_e2e_mean_ms"],
            qms["conditions"]["C4"]["pipeline_warm_e2e_time_ms"]["mean"]
            - qms["conditions"]["C2"]["pipeline_warm_e2e_time_ms"]["mean"],
            rel_tol=1e-12,
        ),
        "canonical_50_of_50_frozen": canonical["hard_gates"]["generated_token_parity_50_of_50"],
        "final_test_suite_95": "95 passed" in (PACK / "final-tests.txt").read_text(encoding="utf-8"),
    }
    payload = {
        "schema": "ccdf.quality-repair-independent-validation.v1",
        "pass": all(checks.values()),
        "checks": checks,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
