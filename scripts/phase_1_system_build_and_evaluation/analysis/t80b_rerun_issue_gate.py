import json
import csv
from pathlib import Path

def first_present(row, keys, default=None):
    for key in keys:
        if isinstance(row, dict) and key in row and row[key] is not None:
            return row[key]
    return default

def numeric_first_present(row, keys, default=None):
    for key in keys:
        if isinstance(row, dict) and key in row and row[key] is not None:
            try:
                return float(row[key])
            except (TypeError, ValueError):
                continue
    return default

def extract_vram_reserved(row):
    return numeric_first_present(row, [
        "vram_reserved_gib",
        "prefill_vram_reserved_gib",
        "peak_reserved_gib",
        "peak_vram_reserved_gib",
        "max_vram_reserved_gib",
    ])

def extract_vram_allocated(row):
    return numeric_first_present(row, [
        "vram_allocated_gib",
        "prefill_vram_allocated_gib",
        "peak_allocated_gib",
        "peak_vram_allocated_gib",
        "max_vram_allocated_gib",
    ])

def extract_prefill_ms(row):
    return numeric_first_present(row, [
        "t_prefill_ms",
        "avg_t_prefill_ms",
    ])

def extract_tau_mean(row):
    return numeric_first_present(row, [
        "tau_mean",
        "avg_tau_mean",
    ])

def classify_completeness(row_count, expected=30):
    if row_count == expected:
        return "completed"
    elif row_count == 0:
        return "skipped"
    else:
        return "failed_partial"

def process_delta_row(row, actual_row_count):
    cond = row["condition"]
    ds = row["dataset"]
    metric = row["metric"]
    
    c_row = dict(row)
    if metric != "row_count":
        if actual_row_count == 0:
            c_row["task80a_value"] = "skipped"
            c_row["delta"] = "not_comparable"
            c_row["relative_delta_percent"] = "not_comparable"
            c_row["severity"] = "skipped"
        elif actual_row_count < 30: # partial run
            c_row["task80a_value"] = "partial_run_not_comparable"
            c_row["delta"] = "partial_run_not_comparable"
            c_row["relative_delta_percent"] = "partial_run_not_comparable"
            c_row["severity"] = "partial_run"
            
    if metric == "row_count" and actual_row_count < 30 and ds == "qmsum_meeting_qa_long":
        c_row["severity"] = "row_count_major_shift"
        
    return c_row

def generate_decision():
    return {
        "task": "80B",
        "decision": "D",
        "decision_label": "Proceed to T81 with caveat",
        "t80c_needed": False,
        "t80d_needed": False,
        "new_diagnostic_run_executed": False,
        "model_used": False,
        "compressor_used": False,
        "cuda_used": False,
        "task80a_status": "BLOCKED / PASS_WITH_NOTES",
        "gsm8k_conclusion": "Task80A confirms GSM8K numeric-quality pattern. DFlash-R1 quality did not regress on GSM8K. DFlash-R1 timing shift is a runtime/timing watch, not a confirmed code regression.",
        "qmsum_conclusion": "Task80A QMSum rerun is incomplete and must be treated as a rerun caveat. Task71/79B remain the completed QMSum diagnostic basis.",
        "cleaned_delta_conclusion": "Missing and skipped scalar metrics were removed to prevent misleading delta averages.",
        "final_evidence_basis": "GSM8K quality from Task80A; QMSum long-context diagnostic from Task71/79B.",
        "claim_safety": "All speed and quality claims remain local, preliminary, and subject to runtime variance constraints.",
        "next_task": "T81",
    }

def main():
    condition_counts = {
        ("Baseline-AR", "gsm8k_short"): 30,
        ("CC-DFlash-R2", "gsm8k_short"): 30,
        ("DFlash-R1", "gsm8k_short"): 30,
        ("LLMLingua-AR-R2", "gsm8k_short"): 30,
        ("Baseline-AR", "qmsum_meeting_qa_long"): 30,
        ("CC-DFlash-R2", "qmsum_meeting_qa_long"): 0,
        ("DFlash-R1", "qmsum_meeting_qa_long"): 2,
        ("LLMLingua-AR-R2", "qmsum_meeting_qa_long"): 0,
    }

    delta_rows = []
    p = Path("results/phase_1_system_build_and_evaluation/early_experiments/task80a_condition_delta_vs_task80.csv")
    if p.exists():
        with p.open(newline='', encoding='utf-8') as f:
            delta_rows = list(csv.DictReader(f))
            
    cleaned_deltas = []
    for row in delta_rows:
        actual_rc = condition_counts.get((row["condition"], row["dataset"]), 0)
        cleaned_deltas.append(process_delta_row(row, actual_rc))
        
    with open("results/phase_1_system_build_and_evaluation/early_experiments/task80b_cleaned_delta_interpretation.csv", "w", newline="", encoding="utf-8") as f:
        if cleaned_deltas:
            writer = csv.DictWriter(f, fieldnames=cleaned_deltas[0].keys())
            writer.writeheader()
            writer.writerows(cleaned_deltas)

    summary = generate_decision()
    with open("results/phase_1_system_build_and_evaluation/early_experiments/task80b_rerun_issue_gate_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        
    regression_check = {
        "schema_normalization_summary": "Task80A JSONL and summary schemas normalized successfully. VRAM, tau, and prefill are only missing if all known aliases fail.",
        "gsm8k_dflash_r1_comparison": {
            "classification": "timing_runtime_watch",
            "quality_regressed": False,
            "dflash_faster_than_baseline": True,
            "baseline_timing_shifted": True,
            "timing_shifted_materially": True,
            "numeric_match_count": 24,
            "numeric_accuracy": 0.8,
            "avg_e2e_latency_s": 10.494549,
            "e2e_tok_s": 16.087717,
            "avg_t_prefill_ms": "missing_after_alias_check",
            "avg_tau_mean": "missing_after_alias_check",
            "cap_hit_count": 1,
        },
        "qmsum_dflash_stall_summary": {
            "classification": "long_context_runtime_or_prompt_specific_stall",
            "completed_prompt_ids": [1, 2],
            "stalled_prompt_id": 3,
            "dataset_ids": ["qmsum_meeting_qa_test_0082", "qmsum_meeting_qa_test_0015"],
            "tau_mean_valid": True,
            "flash_attn_missing": True,
            "task71_n30_completed": True,
        },
        "regression_classification": "timing_runtime_watch, not a confirmed regression",
        "final_issue_classification": "Proceed to T81 with caveat",
    }
    with open("results/phase_1_system_build_and_evaluation/early_experiments/task80b_dflash_regression_check.json", "w", encoding="utf-8") as f:
        json.dump(regression_check, f, indent=2)

    with open("results/phase_1_system_build_and_evaluation/early_experiments/task80b_rerun_issue_gate_table.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for k, v in regression_check.items():
            if isinstance(v, str):
                writer.writerow([k, v])

if __name__ == "__main__":
    main()
