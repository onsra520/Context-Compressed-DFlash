import json
import csv
import logging
from pathlib import Path
from statistics import mean

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

def analyze():
    datasets = ["gsm8k_short", "qmsum_meeting_qa_long"]
    conditions = ["Baseline-AR", "DFlash-R1", "LLMLingua-AR-R2", "CC-DFlash-R2"]
    
    summary = {}
    table_rows = []
    failures = []
    
    # We load the Task 86 checklist limits
    with open("results/task86_rerun_validation_checklist.json", "r") as f:
        checklist = json.load(f)["gate_criteria"]

    all_passed = True

    for dataset in datasets:
        for condition in conditions:
            # Map condition to filename format
            cond_str = condition.lower().replace('-', '_')
            filepath = Path(f"results/task87_{dataset}_{cond_str}_n10.jsonl")
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
            avg_out_tokens = safe_mean([r.get("metrics", {}).get("output_tokens", 0) for r in rows if "output_tokens" in r.get("metrics", {})])
            avg_gen_latency = safe_mean([r.get("metrics", {}).get("generation_time_s", 0) for r in rows if "generation_time_s" in r.get("metrics", {})])
            avg_t_prefill = safe_mean([r.get("metrics", {}).get("t_prefill_ms", 0) for r in rows if "t_prefill_ms" in r.get("metrics", {})])
            avg_t_compress = safe_mean([r.get("metrics", {}).get("t_compress_ms", 0) for r in rows])
            
            # E2E proxy calculation: gen time + prefill + compress
            avg_e2e_latency = avg_gen_latency + (avg_t_prefill / 1000.0) + (avg_t_compress / 1000.0)
            gen_tok_sec = safe_mean([r.get("metrics", {}).get("tok/s", 0) for r in rows if "tok/s" in r.get("metrics", {})])
            e2e_tok_sec = avg_out_tokens / avg_e2e_latency if avg_e2e_latency > 0 else 0
            
            # Additional dataset specific metrics
            numeric_match_count = sum(1 for r in rows if r.get("metrics", {}).get("numeric_match", False))
            numeric_match_rate = numeric_match_count / row_count if row_count > 0 else 0
            overlap_proxy = safe_mean([r.get("metrics", {}).get("overlap_proxy", 0) for r in rows])
            generic_output_count = sum(1 for r in rows if r.get("metrics", {}).get("generic_output", False))
            
            vram_allocated = safe_mean([r.get("metrics", {}).get("vram_allocated_mb", 0) / 1024.0 for r in rows])
            vram_reserved = safe_mean([r.get("metrics", {}).get("vram_reserved_mb", 0) / 1024.0 for r in rows])
            
            # Check gate
            status = "PASS"
            if row_count != 10: status = "FAIL"
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
                "avg_generation_latency_s": avg_gen_latency,
                "avg_e2e_latency_s": avg_e2e_latency,
                "generation_tok_per_sec_weighted": gen_tok_sec,
                "e2e_tok_per_sec_weighted": e2e_tok_sec,
                "avg_t_compress_ms": avg_t_compress,
                "avg_t_prefill_ms": avg_t_prefill,
                "max_vram_allocated_gib": vram_allocated,
                "max_vram_reserved_gib": vram_reserved,
                "numeric_match_count": numeric_match_count if dataset == "gsm8k_short" else None,
                "numeric_match_rate": numeric_match_rate if dataset == "gsm8k_short" else None,
                "overlap_proxy": overlap_proxy if dataset == "qmsum_meeting_qa_long" else None,
                "generic_output_count": generic_output_count if dataset == "qmsum_meeting_qa_long" else None
            }
            
            table_rows.append(stats)
            summary.setdefault(dataset, {})[condition] = stats

    summary["gate_status"] = "PASS" if all_passed else "FAIL"

    # Write summary
    with open("results/task87_n10_gate_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
        
    # Write CSV
    if table_rows:
        keys = table_rows[0].keys()
        with open("results/task87_n10_gate_table.csv", "w", newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(table_rows)
            
    # Write failures
    if failures:
        with open("results/task87_n10_gate_failures.jsonl", "w") as f:
            for fail in failures:
                f.write(json.dumps(fail) + "\n")
                
    logging.info(f"Task 87 Analysis Complete. Gate Status: {summary['gate_status']}")

if __name__ == "__main__":
    analyze()
