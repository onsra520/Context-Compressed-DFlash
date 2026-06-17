# Task 90 — Phase 1 End-to-End Reproduction Rerun

**Status:** BLOCKED

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
The following artifacts successfully completed (3 rows each):
```text
results/phase_1_system_build_and_evaluation/final_reruns/task90_gsm8k_short_baseline_ar_n3.jsonl = 3 rows
results/phase_1_system_build_and_evaluation/final_reruns/task90_gsm8k_short_dflash_r1_n3.jsonl = 3 rows
results/phase_1_system_build_and_evaluation/final_reruns/task90_gsm8k_short_llmlingua_ar_r2_n3.jsonl = 3 rows
results/phase_1_system_build_and_evaluation/final_reruns/task90_gsm8k_short_cc_dflash_r2_n3.jsonl = 3 rows
results/phase_1_system_build_and_evaluation/final_reruns/task90_qmsum_meeting_qa_long_baseline_ar_n3.jsonl = 3 rows
```

## 5. Missing / aborted artifacts
The execution was aborted mid-run. The following artifacts are missing:
```text
task90_qmsum_meeting_qa_long_dflash_r1_n3.jsonl = missing due to segmentation fault
task90_qmsum_meeting_qa_long_llmlingua_ar_r2_n3.jsonl = not run after abort
task90_qmsum_meeting_qa_long_cc_dflash_r2_n3.jsonl = not run after abort
```

## 6. Runtime failure
The reproduction matrix crashed with a **Segmentation fault (core dumped)** during the execution of `qmsum_meeting_qa_long` under the `DFlash-R1` condition.

## 7. Why Phase 1 is not closed
Task 90 is currently blocked. Since Task 90 represents the final end-to-end reproducibility gate for Phase 1, Phase 1 cannot be closed until Task 90 is completed and validated.

## 8. Next required gate: Task90A
A targeted isolation gate (Task 90A) is required to diagnose the QMSum DFlash-R1 segmentation fault and determine if it is a transient sequence sensitivity or an isolated crash.

## 9. Artifact list
* `results/phase_1_system_build_and_evaluation/final_reruns/task90_gsm8k_short_baseline_ar_n3.jsonl`
* `results/phase_1_system_build_and_evaluation/final_reruns/task90_gsm8k_short_cc_dflash_r2_n3.jsonl`
* `results/phase_1_system_build_and_evaluation/final_reruns/task90_gsm8k_short_dflash_r1_n3.jsonl`
* `results/phase_1_system_build_and_evaluation/final_reruns/task90_gsm8k_short_llmlingua_ar_r2_n3.jsonl`
* `results/phase_1_system_build_and_evaluation/final_reruns/task90_qmsum_meeting_qa_long_baseline_ar_n3.jsonl`

## 10. Claim boundary
* Task90 validates post-cleanup reproducibility. It does not replace Task88 controlled n=30 benchmark metrics.
* Task90 is currently blocked by a runtime segmentation fault in QMSum DFlash-R1.
* This does not prove DFlash-R1 is structurally broken.
* no universal speedup claim
* no final correctness claim
* no QMSum semantic correctness claim
* no deployment readiness claim
* no confirmed 8GB claim
* no DFlash-R1 broken claim
