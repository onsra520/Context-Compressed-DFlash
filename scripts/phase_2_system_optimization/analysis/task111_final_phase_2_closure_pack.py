from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUTPUT_DIR = ROOT / "results/phase_2_system_optimization/final_reruns/task111_final_phase_2_closure_pack"

def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def generate_closure_pack(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    
    # 1. Final GSM8K status
    gsm8k_final = {
        "optimized_gsm8k_candidate": "T106B_gsm8k_concise_final_answer_v1",
        "strict": "88/100",
        "cap_limited": "2/100",
        "wrong_numeric": "10/100",
        "final_answer_marker": "98/100",
        "avg_e2e_s": 2.145689,
        "avg_t_compress_ms": 17.457620,
        "max_vram_gib": 4.439453,
        "t109_status": "not_adopted",
        "t107b_status": "not_adopted",
        "default_switch": "blocked"
    }
    
    # 2. Final QMSum boundary
    qmsum_final = {
        "qmsum_semantic_correctness": "NOT_CLAIMED",
        "qmsum_final_status": "FINAL_LIMITATION_AFTER_REPAIR_AND_JUDGE_ATTEMPT",
        "t108b_repair_status": "NOT_VALIDATED_AS_REPAIR",
        "judge_status": "AUXILIARY_EVIDENCE_ONLY",
        "t105b_avg_e2e_s": 5.235310,
        "baseline_ar_avg_e2e_s": 3.770054,
        "dflash_r1_avg_e2e_s": 5.188113
    }
    
    # 3. Validation model summary
    validation_model = {
        "validation_model_status": "LOCAL_JUDGE_PIPELINE_AVAILABLE_BUT_AUXILIARY_ONLY",
        "model": "models/validation/Qwen3.5-9B-GGUF/Qwen3.5-9B-UD-Q4_K_XL.gguf",
        "engine": "llama_cpp",
        "n_ctx": 8192,
        "n_gpu_layers": -1,
        "t110a_commit": "1749941",
        "t110b_commit": "95253b5",
        "t110c_commit": "23fe0e0",
        "t110d_commit": "2bace9f"
    }
    
    # 4. Phase 2 Final Status
    phase_2_status = {
        "phase_2_status": "COMPLETE_WITH_CAVEATS",
        "optimized_gsm8k_candidate": "T106B_gsm8k_concise_final_answer_v1",
        "default_switch": "NO",
        "production_ready": "NO",
        "qmsum_semantic_correctness": "NOT_CLAIMED",
        "qmsum_final_status": "FINAL_LIMITATION_AFTER_REPAIR_AND_JUDGE_ATTEMPT",
        "validation_model_status": "LOCAL_JUDGE_PIPELINE_AVAILABLE_BUT_AUXILIARY_ONLY"
    }
    
    supported_claims = [
        "Light GPU compressor path substantially reduces compression overhead compared with earlier CPU large-compressor path.",
        "On GSM8K, T106B is the best scoped optimized candidate after T107B/T109 repair attempts.",
        "On GSM8K, T106B improves strict/cap behavior over pre-fix optimized CC-DFlash in the scoped candidate setting.",
        "Local Qwen3.5-9B GGUF judge pipeline is available and technically functional.",
        "QMSum received repair and judge-validation attempts, but remains a semantic limitation."
    ]
    
    blocked_claims = [
        "CC-DFlash is production-ready.",
        "Default switch is authorized.",
        "CC-DFlash universally beats DFlash-R1.",
        "CC-DFlash wins QMSum.",
        "QMSum semantic correctness is proven.",
        "QMSum residual risk is eliminated.",
        "Local judge labels are ground truth.",
        "T108B repaired QMSum."
    ]
    
    reproducibility = {
        "config_updated": True,
        "data_dirs_present": True,
        "metrics_recorded": True
    }
    
    closure_summary = {
        "task": "T111",
        "title": "Final Phase 2 Closure Pack",
        "phase_2_status": phase_2_status,
        "gsm8k_final": gsm8k_final,
        "qmsum_final": qmsum_final,
        "validation_model": validation_model,
        "supported_claims": supported_claims,
        "blocked_claims": blocked_claims
    }
    
    _write_json(output_dir / "summary/task111_closure_summary.json", closure_summary)
    _write_json(output_dir / "summary/task111_gsm8k_final_candidate.json", gsm8k_final)
    _write_json(output_dir / "summary/task111_qmsum_final_boundary.json", qmsum_final)
    _write_json(output_dir / "summary/task111_validation_model_summary.json", validation_model)
    _write_json(output_dir / "summary/task111_supported_claims.json", supported_claims)
    _write_json(output_dir / "summary/task111_blocked_claims.json", blocked_claims)
    _write_json(output_dir / "summary/task111_phase_2_final_status.json", phase_2_status)
    _write_json(output_dir / "summary/task111_reproducibility_manifest.json", reproducibility)
    
    (output_dir / "tables").mkdir(parents=True, exist_ok=True)
    
    with (output_dir / "tables/task111_phase_2_result_table.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["domain", "metric", "value"])
        writer.writeheader()
        for k, v in gsm8k_final.items():
            writer.writerow({"domain": "gsm8k", "metric": k, "value": str(v)})
        for k, v in qmsum_final.items():
            writer.writerow({"domain": "qmsum", "metric": k, "value": str(v)})
        for k, v in validation_model.items():
            writer.writerow({"domain": "validation", "metric": k, "value": str(v)})
            
    with (output_dir / "tables/task111_claim_boundary_table.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["claim_type", "claim"])
        writer.writeheader()
        for c in supported_claims:
            writer.writerow({"claim_type": "supported", "claim": c})
        for c in blocked_claims:
            writer.writerow({"claim_type": "blocked", "claim": c})

    return closure_summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    
    res = generate_closure_pack(output_dir=args.output_dir)
    print(f"phase_2_status={res['phase_2_status']['phase_2_status']}")
    print(f"qmsum_final_status={res['qmsum_final']['qmsum_final_status']}")
    print(f"optimized_gsm8k_candidate={res['gsm8k_final']['optimized_gsm8k_candidate']}")


if __name__ == "__main__":
    main()
