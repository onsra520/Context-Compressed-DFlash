# Task105A — GSM8K Controlled Speed Matrix

## 1. Purpose

Task105A runs the controlled GSM8K speed/quality matrix requested by Task104.

The goal is to compare the optimized `CC-DFlash-R2` Light GPU path against matched `Baseline-AR` and `DFlash-R1` references under the same local runtime setup:

- dataset: `gsm8k_short`
- seed: `42`
- n: `100`
- `max_new_tokens=256`
- stored generated text
- resume/no-overwrite JSONL artifacts
- same local RTX 4070 Laptop GPU shell

Task105A did not run QMSum, QMSum n100, a full matrix, Large CPU, LLMLingua-AR-R2, GSM8K n1000/full dataset, query-aware compression, keep-rate tuning, model/config default changes, downloads, human scoring, or an LLM judge.

## 2. Inputs

Task105A used the active `gsm8k_short` dataset because it is the canonical Phase 2 GSM8K controlled dataset used by Task96, Task99-R, and Task100B.

The three controlled artifacts are:

| Condition | Artifact |
| --- | --- |
| `Baseline-AR` | `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/runs/baseline_ar_gsm8k_short_seed42_n100_mnt256.jsonl` |
| `DFlash-R1` | `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/runs/dflash_r1_gsm8k_short_seed42_n100_mnt256.jsonl` |
| `CC-DFlash-R2` Light GPU | `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/runs/cc_dflash_r2_light_gpu_gsm8k_short_seed42_n100_mnt256.jsonl` |

## 3. Setup

The optimized condition used:

- condition: `CC-DFlash-R2`
- compressor profile: `light`
- runtime compressor placement: `--compressor-device-map cuda`
- compressor default config unchanged
- local files only recorded by metadata
- `R_actual=2.00` on average

The reference conditions used no compressor:

- `Baseline-AR`
- `DFlash-R1`

All three runs completed `100/100` rows. No OOM/CUDA failure flags were recorded.

## 4. Controlled Matrix Results

| Condition | Strict proxy | Cap-limited | Wrong numeric | Avg e2e (s) | Avg tok/s | Avg tau | Avg T_compress (ms) | Max VRAM reserved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Baseline-AR` | `85/100` | `8/100` | `7/100` | `4.641074` | `32.103945` | `0.000000` | n/a | `2.894531 GiB` |
| `DFlash-R1` | `84/100` | `9/100` | `7/100` | `2.650564` | `56.628995` | `5.343301` | n/a | `3.814453 GiB` |
| `CC-DFlash-R2` Light GPU | `79/100` | `15/100` | `6/100` | `2.896622` | `59.089889` | `5.630137` | `17.249677` | `4.431641 GiB` |

## 5. Speed Ranking

Task105A ranks conditions by average end-to-end time, lower is better:

1. `DFlash-R1`: `2.650564s`
2. `CC-DFlash-R2` Light GPU: `2.896622s`
3. `Baseline-AR`: `4.641074s`

The optimized Light GPU path was faster than `Baseline-AR` by `1.744452s` on average, or about `37.59%` lower average e2e time.

The optimized Light GPU path was slower than `DFlash-R1` by `0.246058s` on average, or about `9.28%` higher average e2e time.

Therefore Task105A does not support a controlled claim that `CC-DFlash-R2` Light GPU is faster than all matched GSM8K references.

## 6. Quality Proxy

Task105A uses the existing Task95B calibrated deterministic GSM8K numeric proxy.

The optimized Light GPU path reached `79/100` strict proxy, while the references reached:

- `Baseline-AR`: `85/100`
- `DFlash-R1`: `84/100`

The optimized path also had more cap-limited incomplete rows:

- `Baseline-AR`: `8/100`
- `DFlash-R1`: `9/100`
- `CC-DFlash-R2` Light GPU: `15/100`

This means the controlled speed matrix is complete, but it does not support a quality-preserved speed-win claim over the matched references.

## 7. Claim Update

Supported bounded claims:

- Task105A completed a controlled GSM8K-only n100 matrix over `Baseline-AR`, `DFlash-R1`, and `CC-DFlash-R2` Light GPU.
- `CC-DFlash-R2` Light GPU was faster than `Baseline-AR` on average e2e time in this matched GSM8K setup.
- `CC-DFlash-R2` Light GPU preserved low GPU compressor overhead in this matched GSM8K setup, with average `T_compress=17.249677ms`.
- `CC-DFlash-R2` Light GPU completed locally with max reserved VRAM about `4.43GiB` and no recorded OOM/CUDA failure.

Blocked claims:

- final benchmark speedup
- faster than `DFlash-R1`
- faster than all controlled references
- quality-preserved speed-win over the full controlled GSM8K matrix
- QMSum semantic correctness
- QMSum residual-risk elimination
- universal 8GB deployment readiness
- default GPU switch
- `DFlash-R1` broken or invalid

## 8. QMSum Caveat Carryforward

Task105A is GSM8K-only. It does not alter the Task103D/Task104 QMSum caveat:

> QMSum runtime feasibility is measured, but QMSum semantic correctness is not claimed; Task103D closed the deep-fix branch with persistent residual risk.

QMSum remains benchmark-scoped evidence with human-reviewed residual risk, not semantic-correctness proof.

## 9. Artifacts

Generated artifacts:

- `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/summary/task105a_matrix_summary.json`
- `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/summary/task105a_condition_metrics.json`
- `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/summary/task105a_speed_ranking.json`
- `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/summary/task105a_quality_proxy_summary.json`
- `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/summary/task105a_failure_or_resume_audit.json`
- `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/summary/task105a_claim_update.json`
- `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/summary/task105a_next_task_decision.json`
- `results/phase_2_system_optimization/final_reruns/task105a_gsm8k_controlled_speed_matrix/tables/task105a_gsm8k_controlled_speed_matrix.csv`

Analyzer:

- `scripts/phase_2_system_optimization/analysis/task105a_gsm8k_controlled_speed_matrix.py`

Tests:

- `tests/test_task105a_gsm8k_controlled_speed_matrix.py`

## 10. Decision

Decision: `PASS_WITH_CAVEAT`.

Rationale:

- all three controlled GSM8K conditions completed `100/100`
- metadata matched the requested controlled setup
- no OOM/CUDA failure flags were recorded
- controlled ranking and claim boundaries are now explicit
- the optimized path did not beat `DFlash-R1` on average e2e time
- the optimized path trailed both references on strict GSM8K proxy

## 11. Next Task

Next task: `T105B — QMSum Controlled Runtime Matrix`.

T105B should carry forward the Task103D/Task104 QMSum caveat. Task105A does not authorize a full matrix, QMSum n100, default GPU switch, or final speed/quality claim.
