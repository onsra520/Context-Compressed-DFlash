import csv
import json
from pathlib import Path

def test_claim_safety_forbids():
    p = Path("results/phase_1_result/task81_claim_safety_matrix.csv")
    assert p.exists()
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    found_universal_speedup = False
    found_qmsum_semantic = False
    found_deployment = False
    found_8gb = False
    for row in rows:
        claim = row["claim"].lower()
        if "universal speedup" in claim:
            assert row["status"] == "FORBIDDEN"
            found_universal_speedup = True
        if "qmsum semantic correctness" in claim:
            assert row["status"] == "FORBIDDEN"
            found_qmsum_semantic = True
        if "deployment readiness" in claim:
            assert row["status"] == "FORBIDDEN"
            found_deployment = True
        if "8 gb" in claim:
            assert row["status"] == "FORBIDDEN"
            found_8gb = True
    assert found_universal_speedup
    assert found_qmsum_semantic
    assert found_deployment
    assert found_8gb

def test_evidence_basis():
    p = Path("results/phase_1_result/task81_evidence_basis_matrix.csv")
    assert p.exists()
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    found_gsm8k = False
    found_qmsum = False
    for row in rows:
        dim = row["dimension"].lower()
        if "gsm8k numeric quality" in dim:
            assert "numeric" in row["allowed_usage_in_final_report"].lower()
            found_gsm8k = True
        if "qmsum latency" in dim or "qmsum lexical proxy" in dim:
            assert "diagnostic" in row["allowed_usage_in_final_report"].lower() or "proxy" in row["allowed_usage_in_final_report"].lower()
            found_qmsum = True
    assert found_gsm8k
    assert found_qmsum

def test_summary():
    p = Path("results/phase_1_result/task81_final_consistency_audit_summary.json")
    assert p.exists()
    s = json.loads(p.read_text(encoding="utf-8"))
    assert s["ready_for_t82"] is True
    assert s["benchmark_rerun_required"] is False
    assert s["model_used"] is False
    assert s["compressor_used"] is False
    assert s["cuda_used"] is False
    assert s["t80c_needed"] is False
    assert s["t80d_needed"] is False
    assert s["decision"] == "PROCEED_TO_T82_WITH_NOTES"
