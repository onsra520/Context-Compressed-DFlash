# Task 90B — Task90 Isolated Resume

## 1. Objective
Complete the missing Task90 benchmark artifacts after the runtime segfault was isolated.

## 2. Why Task90B was needed after Task90A
Task90 aborted during execution due to a segmentation fault in `qmsum_meeting_qa_long` + `DFlash-R1`. Task90A verified that this crash was transient and runtime-order dependent, rather than a permanent structural breakage. Task90B leverages this finding by using an isolated execution wrapper to bypass the runtime instability and generate the missing benchmark records.

## 3. Missing artifacts resumed
* `task90_qmsum_meeting_qa_long_dflash_r1_n3.jsonl`
* `task90_qmsum_meeting_qa_long_llmlingua_ar_r2_n3.jsonl`
* `task90_qmsum_meeting_qa_long_cc_dflash_r2_n3.jsonl`

## 4. Isolated execution method
A dedicated runner (`scripts/phase_1_system_build_and_evaluation/runners/t90b_resume_missing_qmsum.sh`) was written to execute each of the three missing conditions as independent subprocesses rather than running continuously within the same Python process. This avoids cross-condition memory fragmentation or cumulative runtime states.

## 5. Resume results
All three isolated processes completed without encountering the segmentation fault. Each produced a successfully validated `jsonl` artifact containing exactly `n=3` rows of non-empty JSON data.

## 6. Impact on Task90 status
Task90B completed the missing QMSum artifacts and allows Task90 to move to PASS_WITH_NOTES.

## 7. Artifact list
* `results/phase_1_system_build_and_evaluation/final_reruns/task90_qmsum_meeting_qa_long_dflash_r1_n3.jsonl`
* `results/phase_1_system_build_and_evaluation/final_reruns/task90_qmsum_meeting_qa_long_llmlingua_ar_r2_n3.jsonl`
* `results/phase_1_system_build_and_evaluation/final_reruns/task90_qmsum_meeting_qa_long_cc_dflash_r2_n3.jsonl`
* `results/phase_1_system_build_and_evaluation/repair_and_gate/task90b_qmsum_dflash_r1_resume.log`
* `results/phase_1_system_build_and_evaluation/repair_and_gate/task90b_qmsum_llmlingua_ar_r2_resume.log`
* `results/phase_1_system_build_and_evaluation/repair_and_gate/task90b_qmsum_cc_dflash_r2_resume.log`

## 8. Claim boundary
* Task90B isolates a crash; it does not guarantee final runtime stability without further optimization.
* no universal speedup claim
* no final correctness claim
* no QMSum semantic correctness claim
* no deployment readiness claim
* no confirmed 8GB claim
* no DFlash-R1 broken claim
