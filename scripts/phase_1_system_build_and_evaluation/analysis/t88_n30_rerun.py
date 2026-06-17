import json
import csv
import logging
from pathlib import Path
from statistics import mean, median

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_empty_count(text):
    return 1 if not text or text.strip() == "" else 0

def get_repetition_count(text):
    words = text.split()
    if len(words) > 10 and len(set(words[-10:])) == 1:
        return 1
    return 0

def safe_mean(values):
    return mean(values) if values else 0.0

def safe_median(values):
    return median(values) if values else 0.0

def analyze():
    datasets = ["gsm8k_short", "qmsum_meeting_qa_long"]
    conditions = ["Baseline-AR", "DFlash-R1", "LLMLingua-AR-R2", "CC-DFlash-R2"]
    
    summary = {}
    table_rows = []
    failures = []
    
    # We load the Task 86 checklist limits
    with open("results/phase_1_system_build_and_evaluation/repair_and_gate/task86_rerun_validation_checklist.json", "r") as f:
        checklist = json.load(f)["gate_criteria"]

    all_passed = True

    for dataset in datasets:
        for condition in conditions:
            # Map condition to filename format
            cond_str = condition.lower().replace('-', '_')
            filepath = Path(f"results/task88_{dataset}_{cond_str}_n30.jsonl")
            if not filepath.exists():
                logging.error(f"Missing file: {filepath}")
                failures.append({"dataset": dataset, "condition": condition, "error": "File missing"})
                all_passed = False
                continue
                
            rows = []
            with open(filepath, "r") as f:
                for line in f:
                    if line.strip():
                        rows.append(json.loads(line))
            
            row_count = len(rows)
            empty_count = sum(get_empty_count(r.get("generated_text", "")) for r in rows)
            rep_count = sum(get_repetition_count(r.get("generated_text", "")) for r in rows)
            hit_cap_count = sum(1 for r in rows if r.get("metrics", {}).get("hit_cap", False))
            
            # metrics from jsonl
            def get_val(r, k, default=0.0): return r.get(k, default)
            avg_out_tokens = safe_mean([get_val(r, "output_tokens") for r in rows if "output_tokens" in r])
            median_out_tokens = safe_median([get_val(r, "output_tokens") for r in rows if "output_tokens" in r])
            avg_gen_latency = safe_mean([get_val(r, "generation_time_s") for r in rows if "generation_time_s" in r])
            median_gen_latency = safe_median([get_val(r, "generation_time_s") for r in rows if "generation_time_s" in r])
            avg_t_prefill = safe_mean([get_val(r, "t_prefill_ms") for r in rows if "t_prefill_ms" in r])
            median_t_prefill = safe_median([get_val(r, "t_prefill_ms") for r in rows if "t_prefill_ms" in r])
            avg_t_compress = safe_mean([get_val(r, "t_compress_ms") for r in rows if "t_compress_ms" in r])
            
            # E2E proxy calculation: gen time + prefill + compress
            e2e_latencies = [get_val(r, "generation_time_s") + (get_val(r, "t_prefill_ms") / 1000.0) + (get_val(r, "t_compress_ms") / 1000.0) for r in rows]
            avg_e2e_latency = safe_mean(e2e_latencies)
            median_e2e_latency = safe_median(e2e_latencies)
            gen_tok_sec = safe_mean([get_val(r, "tok_per_sec") for r in rows if "tok_per_sec" in r])
            e2e_tok_sec = avg_out_tokens / avg_e2e_latency if avg_e2e_latency > 0 else 0
            
            # Additional dataset specific metrics
            # GSM8K numeric match
            def check_numeric_match(r):
                expected = r.get("expected_answer", "").strip()
                gen = r.get("generated_text", "")
                if not expected: return False
                return expected in gen
            numeric_match_count = sum(1 for r in rows if check_numeric_match(r))
            numeric_match_rate = numeric_match_count / row_count if row_count > 0 else 0
            
            # QMSum overlap proxy
            def check_overlap(r):
                expected_words = set(r.get("expected_answer", "").lower().split())
                gen_words = set(r.get("generated_text", "").lower().split())
                if not expected_words: return 0.0
                return len(expected_words.intersection(gen_words)) / len(expected_words)
            overlap_proxy = safe_mean([check_overlap(r) for r in rows])
            generic_output_count = None # Not implemented here easily without full LLM-as-a-judge
            
            vram_allocated = safe_mean([get_val(r, "vram_allocated_gib") for r in rows])
            vram_reserved = safe_mean([get_val(r, "vram_reserved_gib") for r in rows])
            
            # Check gate
            status = "PASS"
            if row_count != 30: status = "FAIL"
            if empty_count > checklist["empty_output_count"]["threshold"]: status = "FAIL"
            if rep_count > checklist["repetition_count"]["threshold"]: status = "FAIL"
            if hit_cap_count > checklist["hit_cap_count"]["threshold"]: status = "FAIL"
            
            if status == "FAIL":
                all_passed = False
                failures.append({
                    "dataset": dataset, 
                    "condition": condition,
                    "row_count": row_count,
                    "empty_count": empty_count,
                    "rep_count": rep_count,
                    "hit_cap": hit_cap_count
                })
                
            stats = {
                "dataset": dataset,
                "condition": condition,
                "row_count": row_count,
                "status": status,
                "empty_output_count": empty_count,
                "repetition_count": rep_count,
                "hit_cap_count": hit_cap_count,
                "avg_output_tokens": avg_out_tokens,
                "median_output_tokens": median_out_tokens,
                "avg_generation_latency_s": avg_gen_latency,
                "median_generation_latency_s": median_gen_latency,
                "avg_e2e_latency_s": avg_e2e_latency,
                "median_e2e_latency_s": median_e2e_latency,
                "generation_tok_per_sec_weighted": gen_tok_sec,
                "e2e_tok_per_sec_weighted": e2e_tok_sec,
                "avg_t_compress_ms": avg_t_compress,
                "avg_t_prefill_ms": avg_t_prefill,
                "median_t_prefill_ms": median_t_prefill,
                "max_vram_allocated_gib": vram_allocated,
                "max_vram_reserved_gib": vram_reserved,
                "numeric_match_count": numeric_match_count if dataset == "gsm8k_short" else None,
                "numeric_match_rate": numeric_match_rate if dataset == "gsm8k_short" else None,
                "overlap_proxy": overlap_proxy if dataset == "qmsum_meeting_qa_long" else None,
                "generic_output_count": generic_output_count if dataset == "qmsum_meeting_qa_long" else None
            }
            
            table_rows.append(stats)
            summary.setdefault(dataset, {})[condition] = stats
            
            # Outlier watch for QMSum DFlash-R1
            if dataset == "qmsum_meeting_qa_long" and condition == "DFlash-R1":
                outliers = []
                for r in rows:
                    r_gen = get_val(r, "generation_time_s")
                    r_toks = get_val(r, "tok_per_sec")
                    if r_gen > 2 * median_gen_latency or (median_gen_latency > 0 and r_toks < 0.5 * gen_tok_sec):
                        outliers.append(r)
                
                is_systematic = len(outliers) > 15
                inspection = {
                    "conclusion": "systematic_slowdown" if is_systematic else "outlier_based_slowdown",
                    "details": f"Found {len(outliers)} outliers out of {row_count} rows based on >2x median latency or <50% tok/s.",
                    "rows": [
                        {
                            "prompt_id": r.get("prompt_id"),
                            "generation_time_s": get_val(r, "generation_time_s"),
                            "tok_per_sec": get_val(r, "tok_per_sec"),
                            "output_tokens": get_val(r, "output_tokens"),
                            "t_prefill_ms": get_val(r, "t_prefill_ms"),
                            "t_compress_ms": get_val(r, "t_compress_ms")
                        } for r in outliers
                    ]
                }
                with open("results/phase_1_system_build_and_evaluation/final_reruns/task88_qmsum_dflash_r1_latency_inspection.json", "w") as f:
                    json.dump(inspection, f, indent=2)
                
                if outliers:
                    with open("results/phase_1_system_build_and_evaluation/final_reruns/task88_qmsum_dflash_r1_latency_outliers.jsonl", "w") as f:
                        for r in outliers:
                            f.write(json.dumps(r) + "\n")

    gate_status = "PASS" if all_passed else "FAIL"
    
    # Check for DFlash-R1 slowdown anomaly
    for dataset in datasets:
        baseline_stats = summary.get(dataset, {}).get("Baseline-AR")
        dflash_stats = summary.get(dataset, {}).get("DFlash-R1")
        if baseline_stats and dflash_stats:
            baseline_latency = baseline_stats["avg_e2e_latency_s"]
            dflash_latency = dflash_stats["avg_e2e_latency_s"]
            if baseline_latency > 0 and dflash_latency > baseline_latency * 1.25:
                logging.warning(f"Latency anomaly in {dataset}: DFlash-R1 ({dflash_latency:.2f}s) is >25% slower than Baseline-AR ({baseline_latency:.2f}s)")
                if gate_status == "PASS":
                    gate_status = "PASS_WITH_NOTES"

    summary["gate_status"] = gate_status

    # Write summary
    summary_path = "results/phase_1_system_build_and_evaluation/final_reruns/task88_n30_rerun_summary.json"
    with open(summary_path, "w") as f:
        json.dump({"status": gate_status, "metrics": summary}, f, indent=2)
        
    csv_path = "results/phase_1_system_build_and_evaluation/final_reruns/task88_n30_rerun_table.csv"
    with open(csv_path, "w", newline="") as f:
        if table_rows:
            writer = csv.DictWriter(f, fieldnames=table_rows[0].keys())
            writer.writeheader()
            writer.writerows(table_rows)
            
    if failures:
        failures_path = "results/phase_1_system_build_and_evaluation/final_reruns/task88_n30_rerun_failures.jsonl"
        with open(failures_path, "w") as f:
            for fail in failures:
                f.write(json.dumps(fail) + "\n")
                
    logging.info(f"Task 88 Analysis Complete. Gate Status: {gate_status}")

if __name__ == "__main__":
    analyze()
