import argparse
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_empty_count(text):
    return 1 if not text or text.strip() == "" else 0

def get_repetition_count(text):
    # simplistic heuristic for stuck repetition: same exact word repeated many times at the end
    words = text.split()
    if len(words) > 10 and len(set(words[-10:])) == 1:
        return 1
    return 0

def evaluate_task(task_id, manifest, checklist):
    logging.info(f"Evaluating {task_id}")
    task_def = manifest["tasks"].get(task_id)
    if not task_def:
        logging.error(f"Task {task_id} not found in manifest.")
        return False
        
    target_rows = task_def["n_rows"]
    datasets = manifest["parameters"]["datasets"]
    conditions = manifest["parameters"]["conditions"]
    template = manifest["parameters"]["output_filename_template"]
    
    all_passed = True
    
    for dataset in datasets:
        for condition in conditions:
            # e.g., results/task87_gsm8k_short_baseline_ar_n10.jsonl
            cond_str = condition.lower().replace("-", "_")
            filepath = Path(template.format(task_id=task_id, dataset=dataset, condition=cond_str, n=target_rows))
            if not filepath.exists():
                logging.error(f"[{dataset}][{condition}] File missing: {filepath}")
                all_passed = False
                continue
                
            rows = []
            with open(filepath, "r") as f:
                for line in f:
                    if line.strip():
                        rows.append(json.loads(line))
            
            actual_rows = len(rows)
            if actual_rows != target_rows:
                logging.error(f"[{dataset}][{condition}] Row count mismatch. Expected {target_rows}, got {actual_rows}")
                all_passed = False
                
            empty_count = sum(get_empty_count(r.get("generated_text", "")) for r in rows)
            rep_count = sum(get_repetition_count(r.get("generated_text", "")) for r in rows)
            # Hit cap isn't easily measured here unless stored in the JSONL. Assuming it's in metrics if available.
            hit_cap_count = sum(1 for r in rows if r.get("metrics", {}).get("hit_cap", False))
            
            if empty_count > checklist["gate_criteria"]["empty_output_count"]["threshold"]:
                logging.error(f"[{dataset}][{condition}] Empty outputs exceeded threshold: {empty_count}")
                all_passed = False
                
            if rep_count > checklist["gate_criteria"]["repetition_count"]["threshold"]:
                logging.error(f"[{dataset}][{condition}] Repetitions exceeded threshold: {rep_count}")
                all_passed = False
                
            if hit_cap_count > checklist["gate_criteria"]["hit_cap_count"]["threshold"]:
                logging.error(f"[{dataset}][{condition}] Hit cap exceeded threshold: {hit_cap_count}")
                all_passed = False
                
            # Log successful validation per condition
            logging.info(f"[{dataset}][{condition}] Validated. Rows: {actual_rows}, Empty: {empty_count}, Repetitions: {rep_count}, HitCap: {hit_cap_count}")

    if all_passed:
        logging.info(f"Task {task_id} PASSED the gate criteria.")
    else:
        logging.error(f"Task {task_id} FAILED the gate criteria.")
    return all_passed

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=str, default="task87", help="Task ID to validate (e.g. task87 or task88)")
    args = parser.parse_args()
    
    manifest_path = Path("results/task86_rerun_gate_manifest.json")
    checklist_path = Path("results/task86_rerun_validation_checklist.json")
    
    if not manifest_path.exists() or not checklist_path.exists():
        logging.error("Manifest or checklist JSON files missing. Run Task 86 setup first.")
        return
        
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
    with open(checklist_path, "r") as f:
        checklist = json.load(f)
        
    evaluate_task(args.task, manifest, checklist)

if __name__ == "__main__":
    main()
