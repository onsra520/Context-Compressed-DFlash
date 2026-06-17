import json
import csv
from pathlib import Path
import re

out_dir = Path("results/phase_1_system_build_and_evaluation/repair_and_gate")

experiments = [
    {"name": "task90a_qmsum_dflash_r1_isolated_n1", "slug": "task90a_qmsum_dflash_r1_isolated_n1"},
    {"name": "task90a_qmsum_dflash_r1_isolated_n3", "slug": "task90a_qmsum_dflash_r1_isolated_n3"},
    {"name": "task90a_sequence_1_gsm8k_baseline_n1", "slug": "task90a_sequence_1_gsm8k_baseline_n1"},
    {"name": "task90a_sequence_2_gsm8k_dflash_n1", "slug": "task90a_sequence_2_gsm8k_dflash_n1"},
    {"name": "task90a_sequence_3_qmsum_baseline_n1", "slug": "task90a_sequence_3_qmsum_baseline_n1"},
    {"name": "task90a_sequence_4_qmsum_dflash_n1", "slug": "task90a_sequence_4_qmsum_dflash_n1"},
]

results = []
all_crashes = False
for exp in experiments:
    log_path = out_dir / f"{exp['slug']}.log"
    out_path = out_dir / f"{exp['slug']}.jsonl"
    
    exit_code = None
    crash_detected = False
    segfault_detected = False
    
    if log_path.exists():
        content = log_path.read_text(encoding="utf-8")
        if "Segmentation fault" in content:
            segfault_detected = True
            crash_detected = True
        
        match = re.search(r"Exit code: (\d+)", content)
        if match:
            exit_code = int(match.group(1))
            if exit_code != 0:
                crash_detected = True
    else:
        crash_detected = True

    artifact_exists = out_path.exists()
    row_count = 0
    malformed_count = 0
    empty_count = 0

    if artifact_exists:
        lines = out_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                row_count += 1
                text = row.get("generated_text") or row.get("output_text") or row.get("decoded_text") or row.get("completion") or ""
                if not text:
                    empty_count += 1
            except json.JSONDecodeError:
                malformed_count += 1
    else:
        crash_detected = True

    results.append({
        "experiment_name": exp["name"],
        "output_path": str(out_path),
        "log_path": str(log_path),
        "exit_code": exit_code,
        "artifact_exists": artifact_exists,
        "row_count": row_count,
        "malformed_jsonl_count": malformed_count,
        "empty_output_count": empty_count,
        "crash_detected": crash_detected,
        "segfault_detected": segfault_detected,
    })

conclusion = "INCONCLUSIVE"
isolated_n1 = next((r for r in results if r["experiment_name"] == "task90a_qmsum_dflash_r1_isolated_n1"), None)
seq_dflash = next((r for r in results if r["experiment_name"] == "task90a_sequence_4_qmsum_dflash_n1"), None)

if isolated_n1 and isolated_n1["crash_detected"]:
    conclusion = "CRASHES_WHEN_ISOLATED"
elif seq_dflash and seq_dflash["crash_detected"]:
    conclusion = "PASSES_WHEN_ISOLATED_SEQUENCE_SENSITIVE"
elif isolated_n1 and seq_dflash and not isolated_n1["crash_detected"] and not seq_dflash["crash_detected"]:
    conclusion = "PASSES_SEQUENCE_CHECK"

summary = {
    "conclusion": conclusion,
    "experiments": results
}

with open(out_dir / "task90a_segfault_isolation_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

with open(out_dir / "task90a_segfault_isolation_table.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "experiment_name", "exit_code", "artifact_exists", "row_count", 
        "malformed_jsonl_count", "empty_output_count", "crash_detected", "segfault_detected"
    ])
    writer.writeheader()
    for r in results:
        writer.writerow({
            "experiment_name": r["experiment_name"],
            "exit_code": r["exit_code"],
            "artifact_exists": r["artifact_exists"],
            "row_count": r["row_count"],
            "malformed_jsonl_count": r["malformed_jsonl_count"],
            "empty_output_count": r["empty_output_count"],
            "crash_detected": r["crash_detected"],
            "segfault_detected": r["segfault_detected"]
        })

print(f"Analyzer finished. Conclusion: {conclusion}")
