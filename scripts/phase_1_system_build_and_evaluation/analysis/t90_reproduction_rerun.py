import json
import csv
from pathlib import Path

out_dir = Path("results/phase_1_system_build_and_evaluation/final_reruns")

datasets = ["gsm8k_short", "qmsum_meeting_qa_long"]
conditions = ["baseline_ar", "dflash_r1", "llmlingua_ar_r2", "cc_dflash_r2"]

results = []

for ds in datasets:
    for cond in conditions:
        file_path = out_dir / f"task90_{ds}_{cond}_n3.jsonl"
        
        row_count = 0
        empty_count = 0
        hit_cap_count = 0
        num_match = 0
        overlap_sum = 0
        
        input_tokens = []
        output_tokens = []
        gen_latency = []
        gen_toks = []
        t_compress = []
        t_prefill = []
        comp_ratio = []
        
        warnings = []
        
        if not file_path.exists():
            warnings.append("File missing")
        else:
            lines = file_path.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if not line.strip():
                    continue
                row_count += 1
                row = json.loads(line)
                
                text = row.get("generated_text") or row.get("output_text") or row.get("decoded_text") or row.get("completion") or ""
                if not text.strip():
                    empty_count += 1
                
                metrics = row.get("metrics", {})
                if "input_tokens" in metrics: input_tokens.append(metrics["input_tokens"])
                if "output_tokens" in metrics: output_tokens.append(metrics["output_tokens"])
                if "generation_time_s" in metrics: gen_latency.append(metrics["generation_time_s"])
                if "tok_s" in metrics: gen_toks.append(metrics["tok_s"])
                if "t_compress_ms" in metrics: t_compress.append(metrics["t_compress_ms"])
                if "t_prefill_ms" in metrics: t_prefill.append(metrics["t_prefill_ms"])
                if "compression_ratio" in metrics: comp_ratio.append(metrics["compression_ratio"])
                elif "R_actual" in metrics: comp_ratio.append(metrics["R_actual"])
                
                if metrics.get("hit_cap"):
                    hit_cap_count += 1
                    
                eval_dict = row.get("evaluation", {})
                if ds == "gsm8k_short":
                    if eval_dict.get("numeric_match"):
                        num_match += 1
                else:
                    overlap = eval_dict.get("overlap_score", 0)
                    overlap_sum += overlap
                    
        def avg(lst):
            return sum(lst) / len(lst) if lst else None
            
        avg_input = avg(input_tokens)
        avg_output = avg(output_tokens)
        avg_gen_lat = avg(gen_latency)
        avg_gen_toks = avg(gen_toks)
        avg_t_comp = avg(t_compress)
        avg_t_pref = avg(t_prefill)
        avg_comp = avg(comp_ratio)
        
        if avg_input is None: warnings.append("Missing input_tokens")
        if avg_output is None: warnings.append("Missing output_tokens")
        if avg_gen_lat is None: warnings.append("Missing generation_time_s")
        if avg_gen_toks is None: warnings.append("Missing tok_s")
        
        result_dict = {
            "dataset": ds,
            "condition": cond,
            "status": "PASS" if row_count == 3 else "FAIL",
            "row_count": row_count,
            "avg_input_tokens": round(avg_input, 2) if avg_input else None,
            "avg_output_tokens": round(avg_output, 2) if avg_output else None,
            "avg_generation_latency_s": round(avg_gen_lat, 2) if avg_gen_lat else None,
            "avg_generation_tok_s": round(avg_gen_toks, 2) if avg_gen_toks else None,
            "avg_t_compress_ms": round(avg_t_comp, 2) if avg_t_comp else None,
            "avg_t_prefill_ms": round(avg_t_pref, 2) if avg_t_pref else None,
            "compression_ratio": round(avg_comp, 2) if avg_comp else None,
            "empty_output_count": empty_count,
            "hit_cap_count": hit_cap_count,
            "warnings": "; ".join(warnings)
        }
        
        if ds == "gsm8k_short":
            result_dict["numeric_match_count"] = num_match
            result_dict["numeric_match_rate"] = round(num_match / row_count, 2) if row_count else 0
        else:
            result_dict["avg_overlap_proxy"] = round(overlap_sum / row_count, 2) if row_count else 0
            
        results.append(result_dict)

summary_path = out_dir / "task90_reproduction_summary.json"
csv_path = out_dir / "task90_reproduction_table.csv"

with open(summary_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

fieldnames = [
    "dataset", "condition", "status", "row_count", "avg_input_tokens", "avg_output_tokens",
    "avg_generation_latency_s", "avg_generation_tok_s", "avg_t_compress_ms", "avg_t_prefill_ms",
    "compression_ratio", "empty_output_count", "hit_cap_count", "numeric_match_count",
    "numeric_match_rate", "avg_overlap_proxy", "warnings"
]

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for r in results:
        # make sure to output blanks for missing fields for cleanly formatted CSV
        row_out = {k: r.get(k, "") for k in fieldnames}
        writer.writerow(row_out)

print("Task 90 Analyzer completed successfully.")
