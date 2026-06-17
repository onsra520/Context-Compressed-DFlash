# Task 90 — Phase 1 End-to-End Reproduction Rerun

**Status:** PASS_WITH_NOTES

## 1. Objective
Run the Phase 1 end-to-end reproduction rerun after the Task 89 cleanup to validate that the cleaned repository can reproduce the active Phase 1 pipeline from data fetch to final benchmark execution.

## 2. Data pipeline rerun result
The canonical data pipeline was successfully reproduced. Running:
```bash
PYTHONPATH=src .venv/bin/python scripts/fetch_dataset.py --dataset all_active --stage all --max-samples 100 --seed 42
```
reproduced `data/raw`, `data/processed`, and `data/eval` with zero diff.

## 3. Task90 reproduction setup
The benchmark reproduction was set up to run `n=3` over the `gsm8k_short` and `qmsum_meeting_qa_long` datasets across four conditions (`Baseline-AR`, `DFlash-R1`, `LLMLingua-AR-R2`, `CC-DFlash-R2`).

## 4. Completed artifacts
The following eight artifacts successfully completed (3 rows each):
```text
results/phase_1_system_build_and_evaluation/final_reruns/task90_gsm8k_short_baseline_ar_n3.jsonl
results/phase_1_system_build_and_evaluation/final_reruns/task90_gsm8k_short_dflash_r1_n3.jsonl
results/phase_1_system_build_and_evaluation/final_reruns/task90_gsm8k_short_llmlingua_ar_r2_n3.jsonl
results/phase_1_system_build_and_evaluation/final_reruns/task90_gsm8k_short_cc_dflash_r2_n3.jsonl
results/phase_1_system_build_and_evaluation/final_reruns/task90_qmsum_meeting_qa_long_baseline_ar_n3.jsonl
results/phase_1_system_build_and_evaluation/final_reruns/task90_qmsum_meeting_qa_long_dflash_r1_n3.jsonl
results/phase_1_system_build_and_evaluation/final_reruns/task90_qmsum_meeting_qa_long_llmlingua_ar_r2_n3.jsonl
results/phase_1_system_build_and_evaluation/final_reruns/task90_qmsum_meeting_qa_long_cc_dflash_r2_n3.jsonl
```

## 5. Runtime failure and Isolation (Task90A & Task90B)
The reproduction matrix initially crashed with a **Segmentation fault (core dumped)** during the execution of `qmsum_meeting_qa_long` under the `DFlash-R1` condition.
Task90A isolated the QMSum DFlash-R1 crash and confirmed it was a transient/runtime-order dependent segfault, likely caused by GPU memory fragmentation.
Task90B then completed the missing QMSum artifacts with isolated per-condition execution successfully.

## 6. Metric Summary
A full metric summary has been generated for the reproduction runs at:
* `results/phase_1_system_build_and_evaluation/final_reruns/task90_reproduction_summary.json`
* `results/phase_1_system_build_and_evaluation/final_reruns/task90_reproduction_table.csv`

## 7. Claim boundary
* Task90 validates post-cleanup reproducibility. It does not replace Task88 controlled n=30 benchmark metrics.
* Phase 1 can close only with caveats: Task88 remains the metric evidence; Task90 confirms post-cleanup reproducibility; QMSum remains diagnostic-only; transient runtime-order segfault was isolated and worked around using isolated execution.
* no universal speedup claim
* no final correctness claim
* no QMSum semantic correctness claim
* no deployment readiness claim
* no confirmed 8GB claim
* no DFlash-R1 broken claim
