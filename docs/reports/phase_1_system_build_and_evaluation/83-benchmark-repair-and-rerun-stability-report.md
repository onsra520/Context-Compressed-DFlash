# Task 83 — Benchmark Repair and Rerun Stability Report

## 1. Objective

Repair and verify the benchmark issues currently blocking final metric selection:

* **GSM8K**: DFlash-R1 had a timing/runtime anomaly in the Task80A rerun. We reran `n=30` to verify whether timing returns to the expected pattern or still requires a `runtime_watch`.
* **QMSum**: The latest rerun was incomplete due to DFlash-R1 stalling at `prompt_id=3`. We investigated the issue and reran all four conditions at `n=30`.

## 2. GSM8K DFlash-R1 repair result

The rerun of GSM8K for DFlash-R1 completed successfully with 30/30 rows.

* **Accuracy:** 24/30 numeric matches, equal to a 0.80 numeric match rate.
* **Timing:** The e2e latency returned to the expected speed-reference pattern, measuring an average of 2.96 s and 57.10 e2e tok/s.
* **Conclusion:** The timing anomaly observed in the Task80A rerun is best treated as transient backend/runtime variance, not as a structural DFlash-R1 regression. The GSM8K DFlash-R1 repair result is marked as `stable`.

## 3. QMSum incomplete rerun diagnosis

The previous Task80A QMSum rerun for DFlash-R1 stopped at `prompt_id=3` after a prolonged no-progress interval with GPU activity. Since the run configuration has no internal timeout, the most likely causes are an external kill, a runtime stall, memory pressure, or an extreme prompt-specific generation stall. Task 83 reran the full QMSum suite to determine whether the issue is reproducible.

## 4. QMSum repair rerun result

The full QMSum rerun completed successfully for all four conditions, with 30/30 rows each.

* **Baseline-AR:** 15.32 e2e tok/s.
* **DFlash-R1:** 20.00 e2e tok/s.
* **LLMLingua-AR-R2:** 8.89 e2e tok/s.
* **CC-DFlash-R2:** 10.08 e2e tok/s.

**Conclusion:** DFlash-R1 completed successfully in the repaired QMSum rerun, supporting the interpretation that the prior 2-row stall was an isolated runtime/environment anomaly rather than a reproducible algorithmic failure on long-context inputs. CC-DFlash-R2 remains faster than LLMLingua-AR-R2 in the compressed path. The QMSum repair rerun is marked as `stable`.

## 5. Artifact list

* `results/phase_1_system_build_and_evaluation/repair_and_gate/task83_gsm8k_dflash_r1_repair_n30.jsonl`
* `results/phase_1_system_build_and_evaluation/repair_and_gate/task83_gsm8k_dflash_r1_repair_summary.json`
* `results/phase_1_system_build_and_evaluation/repair_and_gate/task83_gsm8k_dflash_r1_repair_table.csv`
* `results/phase_1_system_build_and_evaluation/repair_and_gate/task83_qmsum_baseline_ar_n30.jsonl`
* `results/phase_1_system_build_and_evaluation/repair_and_gate/task83_qmsum_dflash_r1_n30.jsonl`
* `results/phase_1_system_build_and_evaluation/repair_and_gate/task83_qmsum_llmlingua_ar_r2_n30.jsonl`
* `results/phase_1_system_build_and_evaluation/repair_and_gate/task83_qmsum_cc_dflash_r2_n30.jsonl`
* `results/phase_1_system_build_and_evaluation/repair_and_gate/task83_qmsum_repair_summary.json`
* `results/phase_1_system_build_and_evaluation/repair_and_gate/task83_qmsum_repair_table.csv`
* `scripts/phase_1_system_build_and_evaluation/analysis/t83_repair.py`

## 6. Decision on metric source replacement

Because both repair runs completed successfully, Task83 becomes the updated repaired rerun reference for the affected metrics.

### GSM8K

Task83 replaces the temporary Task69 DFlash-R1 speed reference for repaired DFlash-R1 timing. The new DFlash-R1 result returns to the expected pattern: 24/30 numeric matches, 2.96 s average e2e latency, and 57.10 e2e tok/s.

### QMSum

Task83 replaces Task71 as the current complete `n=30` QMSum four-condition rerun reference. All four conditions completed 30/30 rows. The repaired rerun supports the expected local pattern: DFlash-R1 is faster than Baseline-AR, and CC-DFlash-R2 is faster than LLMLingua-AR-R2 in the compressed path.

Task80A remains a historical rerun caveat, not the active metric source.

## 7. Claim boundary after Task83

* No universal speedup is claimed.
* No final correctness is claimed.
* No QMSum semantic correctness is claimed.
* No deployment readiness or confirmed 8GB deployment is claimed.
* DFlash-R1 is not claimed to be structurally broken.
* QMSum remains a long-context diagnostic benchmark, not semantic-quality evidence.
* Task83 supports a repaired local timing/stability interpretation, not a production-level speedup claim.
